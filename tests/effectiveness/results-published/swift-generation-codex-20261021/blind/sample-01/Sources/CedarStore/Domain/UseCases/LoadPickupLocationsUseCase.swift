import Foundation

struct LoadPickupLocationsUseCase {
    private let repository: any PickupLocationsRepository

    init(repository: any PickupLocationsRepository) { self.repository = repository }

    func execute(postcode: String) async -> ShopResult<[PickupLocation]> {
        guard !postcode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return .issue(.invalidIdentifier)
        }
        return await repository.load(postcode: postcode)
    }
}
