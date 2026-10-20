struct ReceiptLoader {
    let gateway: ReceiptGateway
    func run(id: String) async -> String? { await gateway.fetch(id: id) }
}
