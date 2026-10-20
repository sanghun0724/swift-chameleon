import Foundation

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
