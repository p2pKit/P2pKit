import Foundation

private func stopWithoutObservation(_ status: Int32) -> Never {
    FileHandle.standardError.write(Data("P2PKIT_LAN_DNS_SD_ENDPOINT_JOIN_OBSERVATION_UNAVAILABLE\n".utf8))
    exit(status)
}

// The token is a private invocation join, not a result or a discovered endpoint identifier.
guard CommandLine.arguments.count == 5, CommandLine.arguments[1] == "--token",
      CommandLine.arguments[3] == "--browser-descriptor",
      let policy = LanProbe.DescriptorPolicy(rawValue: CommandLine.arguments[4]),
      policy == .bonjour,
      let probe = LanProbe(policy: policy, token: CommandLine.arguments[2]) else {
    stopWithoutObservation(64)
}
let token = CommandLine.arguments[2]
let accepted = probe.start { text in
    guard !text.isEmpty, text.utf8.count <= 6_144,
          let object = try? JSONSerialization.jsonObject(with: Data(text.utf8)),
          let result = object as? [String: Any], result["mode"] as? String == "cli",
          result["browserDescriptor"] as? String == policy.rawValue else {
        stopWithoutObservation(70)
    }
    let envelope: [String: Any] = ["schema": 1, "token": token,
                                   "browserDescriptor": policy.rawValue, "probe": result]
    guard JSONSerialization.isValidJSONObject(envelope),
          let data = try? JSONSerialization.data(withJSONObject: envelope, options: [.sortedKeys]),
          data.count <= 8_192 else {
        stopWithoutObservation(70)
    }
    var output = Data("P2PKIT_LAN_DNS_SD_ENDPOINT_JOIN_V1 ".utf8)
    output.append(data)
    output.append(0x0a)
    do {
        try FileHandle.standardOutput.write(contentsOf: output)
    } catch {
        stopWithoutObservation(74)
    }
    // A well-formed negative is data, not qualification. The controller still requires cleanup.
    exit(0)
}
guard accepted else { stopWithoutObservation(70) }
dispatchMain()
