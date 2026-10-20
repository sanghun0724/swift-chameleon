struct CustomerLoader {
    let gateway: CustomerGateway
    func run(id: String) async -> String? { await gateway.fetch(id: id) }
}
