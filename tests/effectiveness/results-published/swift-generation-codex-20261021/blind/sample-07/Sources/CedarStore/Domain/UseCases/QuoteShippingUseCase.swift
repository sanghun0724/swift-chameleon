import Foundation

struct QuoteShippingUseCase {
    private let repository: any ShippingQuoteRepository

    init(repository: any ShippingQuoteRepository) { self.repository = repository }

    func execute(orderID: String) async -> ShopResult<ShippingQuote> {
        guard !orderID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return .issue(.invalidIdentifier)
        }
        return await repository.quote(orderID: orderID)
    }
}
