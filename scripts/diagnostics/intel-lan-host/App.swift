import Foundation
import UIKit

@main
final class LanHostAppDelegate: UIResponder, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        true
    }
}

final class LanHostSceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }
        let window = UIWindow(windowScene: windowScene)
        window.rootViewController = LanHostViewController()
        window.makeKeyAndVisible()
        self.window = window
    }
}

final class LanHostViewController: UIViewController {
    private let status = UILabel()
    private let result = UILabel()
    private let begin = UIButton(type: .system)
    private var probe: LanProbe?
    private var startAttempted = false

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        status.text = "READY"
        status.accessibilityIdentifier = "lan-probe-status"
        result.text = "No result yet"
        result.accessibilityIdentifier = "lan-probe-result"
        result.isAccessibilityElement = true
        begin.setTitle("Begin Probe", for: .normal)
        begin.accessibilityIdentifier = "lan-probe-begin"
        begin.addTarget(self, action: #selector(beginProbe), for: .touchUpInside)
        let stack = UIStackView(arrangedSubviews: [status, begin, result])
        stack.axis = .vertical
        stack.spacing = 24
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: view.safeAreaLayoutGuide.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.safeAreaLayoutGuide.centerYAnchor),
            stack.leadingAnchor.constraint(greaterThanOrEqualTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 20),
            stack.trailingAnchor.constraint(lessThanOrEqualTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -20),
        ])
    }

    @objc private func beginProbe() {
        guard !startAttempted else { return }
        startAttempted = true
        begin.isEnabled = false
        guard let token = ProcessInfo.processInfo.environment["P2PKIT_LAN_HOST_TOKEN"],
              let owned = LanProbe(policy: .withTXT, token: token, mode: .app) else {
            status.text = "INVALID_TOKEN"
            return
        }
        probe = owned
        // The shared implementation owns the one 30-second window and its bounded cancellation drain.
        let accepted = owned.start { [weak self] json in
            guard let self else { return }
            guard !json.isEmpty, json.utf8.count <= 6144 else {
                self.status.text = "INVALID_RESULT"
                return
            }
            self.result.text = "Probe result ready"
            self.result.accessibilityLabel = json
            self.status.text = "COMPLETE"
        }
        status.text = accepted ? "RUNNING" : "START_REFUSED"
    }
}
