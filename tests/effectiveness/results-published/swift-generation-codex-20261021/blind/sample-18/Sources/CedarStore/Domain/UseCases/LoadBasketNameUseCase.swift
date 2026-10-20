import Foundation

struct LoadBasketNameUseCase {
    private let repository: any BasketNameRepository

    init(repository: any BasketNameRepository) { self.repository = repository }

    func execute(id: String) async -> ShopResult<String> {
        guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return .issue(.invalidIdentifier)
        }
        return await repository.load(id: id)
    }
}
