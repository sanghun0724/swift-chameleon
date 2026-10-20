import Foundation

struct LoadOrderSummaryUseCase {
    private let repository: any OrderSummaryRepository

    init(repository: any OrderSummaryRepository) { self.repository = repository }

    func execute(id: String) async -> ShopResult<String> {
        guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return .issue(.invalidIdentifier)
        }
        return await repository.load(id: id)
    }
}
