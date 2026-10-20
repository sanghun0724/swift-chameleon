"""Independent Swift package and held checks for the generation study."""

from __future__ import annotations

import subprocess
from pathlib import Path

PROMPTS = {
    "shipping": (
        "Add shipping quotes to CedarStore. Expose "
        "StoreGraph.quoteShipping.execute(orderID:) async -> ShopResult<ShippingQuote>. "
        "Use ShopAPI.shippingQuote(orderID:). A quote must preserve cents and currency; "
        "negative cents or empty currency means invalidPayload. A blank or whitespace-only "
        "order ID means invalidIdentifier without calling the API. Forward a nonblank ID "
        "unchanged. Preserve transport failure mapping. Keep the existing features working. "
        "Implement the code and give a short design note."
    ),
    "pickup": (
        "Add pickup location discovery to CedarStore. Expose "
        "StoreGraph.loadPickupLocations.execute(postcode:) async -> ShopResult<[PickupLocation]>. "
        "Use ShopAPI.pickupLocations(postcode:). Return active locations with nonnegative "
        "capacity, keeping the first eligible entry for each ID, ordered by ascending "
        "title with ID as the tie breaker. A blank or whitespace-only postcode means "
        "invalidIdentifier without calling the API. Forward a nonblank postcode unchanged. "
        "Preserve transport failure mapping. Keep the existing features working. "
        "Implement the code and give a short design note."
    ),
}

COMMON = """import Foundation

enum ShopIssue: Equatable {
    case unavailable
    case unauthorized
    case invalidPayload
    case invalidIdentifier
}

enum ShopResult<Value> {
    case value(Value)
    case issue(ShopIssue)
}

enum TransportIssue {
    case offline
    case forbidden
}

enum TransportReply<Value> {
    case payload(Value)
    case failure(TransportIssue)

    func domain<Mapped>(_ transform: (Value) -> Mapped?) -> ShopResult<Mapped> {
        switch self {
        case .payload(let value):
            guard let mapped = transform(value) else { return .issue(.invalidPayload) }
            return .value(mapped)
        case .failure(.offline):
            return .issue(.unavailable)
        case .failure(.forbidden):
            return .issue(.unauthorized)
        }
    }
}

struct ShippingQuote: Equatable {
    let cents: Int
    let currency: String

    init?(dto: ShippingQuoteDTO) {
        guard dto.cents >= 0, !dto.currency.isEmpty else { return nil }
        cents = dto.cents
        currency = dto.currency
    }
}

struct PickupLocation: Equatable {
    let id: String
    let title: String
    let capacity: Int
}

enum PickupCatalog {
    static func available(_ rows: [PickupLocationDTO]) -> [PickupLocation] {
        var identifiers = Set<String>()
        return rows.compactMap { row in
            guard row.active, row.capacity >= 0,
                  identifiers.insert(row.id).inserted else { return nil }
            return PickupLocation(id: row.id, title: row.title, capacity: row.capacity)
        }.sorted { ($0.title, $0.id) < ($1.title, $1.id) }
    }
}

struct ShippingQuoteDTO { let cents: Int; let currency: String }
struct PickupLocationDTO { let id: String; let title: String; let capacity: Int; let active: Bool }

protocol ShopAPI {
    func orderSummary(id: String) async -> TransportReply<String>
    func accountName(id: String) async -> TransportReply<String>
    func basketName(id: String) async -> TransportReply<String>
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO>
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]>
}
"""


def current_files(role: str, method: str) -> dict[str, str]:
    return {
        f"Domain/Repositories/{role}Repository.swift": f"""protocol {role}Repository {{
    func load(id: String) async -> ShopResult<String>
}}
""",
        f"Data/Repositories/Live{role}Repository.swift": f"""struct Live{role}Repository: {role}Repository {{
    private let api: any ShopAPI

    init(api: any ShopAPI) {{ self.api = api }}

    func load(id: String) async -> ShopResult<String> {{
        await api.{method}(id: id).domain {{ $0.isEmpty ? nil : $0 }}
    }}
}}
""",
        f"Domain/UseCases/Load{role}UseCase.swift": f"""import Foundation

struct Load{role}UseCase {{
    private let repository: any {role}Repository

    init(repository: any {role}Repository) {{ self.repository = repository }}

    func execute(id: String) async -> ShopResult<String> {{
        guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {{
            return .issue(.invalidIdentifier)
        }}
        return await repository.load(id: id)
    }}
}}
""",
    }


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def git(root: Path, *args: str, date: str | None = None) -> str:
    import os

    env = os.environ.copy()
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Cedar Maintainer",
            "-c",
            "user.email=cedar@example.invalid",
            *args,
        ],
        cwd=root,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def create_fixture(root: Path) -> str:
    root.mkdir(parents=True)
    write(
        root,
        "Package.swift",
        """// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "CedarStore", products: [.library(name: "CedarStore", targets: ["CedarStore"])], targets: [.target(name: "CedarStore")])
""",
    )
    write(
        root,
        "README.md",
        "# CedarStore\n\nDomain operations for a small shop. Sources live in Sources/CedarStore.\n",
    )
    write(root, ".gitignore", ".build/\n.swiftpm/\n")
    write(root, "Sources/CedarStore/Domain/ShopTypes.swift", COMMON)
    for role, method in (("Receipt", "orderSummary"), ("Customer", "accountName")):
        write(
            root,
            f"Sources/CedarStore/Legacy/{role}Gateway.swift",
            f"""struct {role}Gateway {{
    let api: any ShopAPI
    func fetch(id: String) async -> String? {{
        switch await api.{method}(id: id) {{
        case .payload(let value): return value
        case .failure: return nil
        }}
    }}
}}
""",
        )
        write(
            root,
            f"Sources/CedarStore/Legacy/{role}Loader.swift",
            f"""struct {role}Loader {{
    let gateway: {role}Gateway
    func run(id: String) async -> String? {{ await gateway.fetch(id: id) }}
}}
""",
        )
    git(root, "init", "-q")
    git(root, "add", ".")
    git(
        root,
        "commit",
        "-q",
        "-m",
        "Add initial shop operations",
        date="2025-01-10T12:00:00Z",
    )
    for role, method in (
        ("OrderSummary", "orderSummary"),
        ("AccountName", "accountName"),
        ("BasketName", "basketName"),
    ):
        for relative, content in current_files(role, method).items():
            write(root, "Sources/CedarStore/" + relative, content)
    write(
        root,
        "Sources/CedarStore/Composition/StoreGraph.swift",
        """struct StoreGraph {
    private let api: any ShopAPI

    init(api: any ShopAPI) { self.api = api }

    var loadOrderSummary: LoadOrderSummaryUseCase {
        LoadOrderSummaryUseCase(repository: LiveOrderSummaryRepository(api: api))
    }

    var loadAccountName: LoadAccountNameUseCase {
        LoadAccountNameUseCase(repository: LiveAccountNameRepository(api: api))
    }

    var loadBasketName: LoadBasketNameUseCase {
        LoadBasketNameUseCase(repository: LiveBasketNameRepository(api: api))
    }
}
""",
    )
    git(root, "add", ".")
    git(
        root,
        "commit",
        "-q",
        "-m",
        "Adopt domain results and repository boundaries",
        date="2026-09-21T12:00:00Z",
    )
    legacy = root / "Sources/CedarStore/Legacy/ReceiptGateway.swift"
    legacy.write_text(
        legacy.read_text()
        .replace("let api:", "private let api:")
        .replace(
            "    func fetch",
            "    init(api: any ShopAPI) { self.api = api }\n\n    func fetch",
        )
    )
    git(root, "add", ".")
    git(
        root,
        "commit",
        "-q",
        "-m",
        "Tidy receipt gateway member visibility",
        date="2026-10-20T12:00:00Z",
    )
    return git(root, "rev-parse", "HEAD").strip()


DRIVER = """import Foundation

final class ShopStub: ShopAPI {
    var calls: [String] = []
    var shipping: TransportReply<ShippingQuoteDTO> = .payload(.init(cents: 250, currency: "USD"))
    var pickup: TransportReply<[PickupLocationDTO]> = .payload([])
    func orderSummary(id: String) async -> TransportReply<String> { .payload("order:" + id) }
    func accountName(id: String) async -> TransportReply<String> { .payload("account:" + id) }
    func basketName(id: String) async -> TransportReply<String> { .payload("basket:" + id) }
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> { calls.append(orderID); return shipping }
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> { calls.append(postcode); return pickup }
}

@main struct Main {
    static func main() async {
        let api = ShopStub()
        let graph = StoreGraph(api: api)
        if case .value("order:42") = await graph.loadOrderSummary.execute(id: "42") {} else { fatalError("existing order") }
        if case .value("account:42") = await graph.loadAccountName.execute(id: "42") {} else { fatalError("existing account") }
        if case .value("basket:42") = await graph.loadBasketName.execute(id: "42") {} else { fatalError("existing basket") }
        TASK_BODY
        print("behavior passed")
    }
}
"""

SHIPPING_BODY = """
        if case .value(let value) = await graph.quoteShipping.execute(orderID: " 42 ") {
            precondition(value.cents == 250 && value.currency == "USD", "shipping fields")
        } else { fatalError("shipping success") }
        precondition(api.calls == [" 42 "], "identifier forwarding")
        if case .issue(.invalidIdentifier) = await graph.quoteShipping.execute(orderID: " \\n\\t") {} else { fatalError("blank identifier") }
        precondition(api.calls.count == 1, "blank avoids API")
        api.shipping = .failure(.offline)
        if case .issue(.unavailable) = await graph.quoteShipping.execute(orderID: "42") {} else { fatalError("offline mapping") }
        api.shipping = .failure(.forbidden)
        if case .issue(.unauthorized) = await graph.quoteShipping.execute(orderID: "42") {} else { fatalError("authorization mapping") }
        api.shipping = .payload(.init(cents: -1, currency: "USD"))
        if case .issue(.invalidPayload) = await graph.quoteShipping.execute(orderID: "42") {} else { fatalError("negative amount") }
        api.shipping = .payload(.init(cents: 0, currency: ""))
        if case .issue(.invalidPayload) = await graph.quoteShipping.execute(orderID: "42") {} else { fatalError("empty currency") }
        api.shipping = .payload(.init(cents: 0, currency: "EUR"))
        if case .value(let value) = await graph.quoteShipping.execute(orderID: "42") { precondition(value.cents == 0 && value.currency == "EUR") } else { fatalError("zero amount") }
"""

PICKUP_BODY = """
        api.pickup = .payload([
            .init(id: "b", title: "North", capacity: 0, active: true),
            .init(id: "a", title: "North", capacity: 2, active: true),
            .init(id: "b", title: "Changed", capacity: 9, active: true),
            .init(id: "c", title: "Closed", capacity: 2, active: false),
            .init(id: "d", title: "Bad", capacity: -1, active: true),
            .init(id: "d", title: "South", capacity: 3, active: true)
        ])
        if case .value(let values) = await graph.loadPickupLocations.execute(postcode: " AB1 ") {
            precondition(values.map(\\.id) == ["a", "b", "d"], "filter order and deduplication")
            precondition(values.map(\\.capacity) == [2, 0, 3], "capacity preservation")
        } else { fatalError("pickup success") }
        precondition(api.calls == [" AB1 "], "postcode forwarding")
        if case .issue(.invalidIdentifier) = await graph.loadPickupLocations.execute(postcode: " \\n\\t") {} else { fatalError("blank postcode") }
        precondition(api.calls.count == 1, "blank avoids API")
        api.pickup = .failure(.offline)
        if case .issue(.unavailable) = await graph.loadPickupLocations.execute(postcode: "AB1") {} else { fatalError("offline mapping") }
        api.pickup = .failure(.forbidden)
        if case .issue(.unauthorized) = await graph.loadPickupLocations.execute(postcode: "AB1") {} else { fatalError("authorization mapping") }
        api.pickup = .payload([])
        if case .value(let values) = await graph.loadPickupLocations.execute(postcode: "AB1") { precondition(values.isEmpty) } else { fatalError("empty collection") }
"""


def behavior_source(task: str) -> str:
    return DRIVER.replace("TASK_BODY", SHIPPING_BODY if task == "shipping" else PICKUP_BODY)
