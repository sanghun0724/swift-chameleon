struct StoreGraph {
    private let api: any ShopAPI

    init(api: any ShopAPI) { self.api = api }

    var quoteShipping: QuoteShippingUseCase {
        QuoteShippingUseCase(repository: LiveShippingQuoteRepository(api: api))
    }

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
