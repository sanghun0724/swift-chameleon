import Foundation

struct LoadAccountNameUseCase {
    private let repository: any AccountNameRepository

    init(repository: any AccountNameRepository) { self.repository = repository }

    func execute(id: String) async -> ShopResult<String> {
        guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return .issue(.invalidIdentifier)
        }
        return await repository.load(id: id)
    }
}
