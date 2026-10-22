import CoreGraphics

// A transitioning accessibility key may have no usable hit-test geometry.
// Unknown is neither ready for input nor proof that Done dismissed the keyboard.
enum KeyboardReadiness: Equatable {
    case hittable
    case notHittable
    case indeterminate

    @MainActor
    static func observe<Key>(
        _ keys: [Key],
        exists: (Key) -> Bool,
        frame: (Key) -> CGRect,
        isHittable: (Key) -> Bool
    ) -> KeyboardReadiness {
        var hasUnknownKey = false
        for key in keys {
            guard exists(key) else { continue }
            let bounds = frame(key)
            let coordinates = [bounds.origin.x, bounds.origin.y, bounds.size.width,
                               bounds.size.height, bounds.maxX, bounds.maxY]
            // CGRect.infinite can use finite sentinel coordinates on Apple.
            guard !bounds.isNull, !bounds.isInfinite, coordinates.allSatisfy(\.isFinite),
                  bounds.size.width > 0, bounds.size.height > 0 else {
                hasUnknownKey = true
                continue
            }
            // Do not replace the actual hit test with a geometry-only guess.
            if isHittable(key) { return .hittable }
        }
        return hasUnknownKey ? .indeterminate : .notHittable
    }
}

// Passive counters for input admission only. The original dismissal observer
// above deliberately keeps its indexed, current-key semantics.
struct KeyboardInputObservation: Equatable {
    let state: KeyboardReadiness
    let keys: Int
    let examined: Int
    let existing: Int
    let invalidGeometry: Int
    let hitTests: Int
    let hittable: Int

    var diagnostic: String {
        let label: String
        switch state {
        case .hittable: label = "HITTABLE"
        case .notHittable: label = "NOT_HITTABLE"
        case .indeterminate: label = "INDETERMINATE"
        }
        return "state=\(label) keys=\(keys) examined=\(examined) existing=\(existing) " +
            "invalidGeometry=\(invalidGeometry) hitTests=\(hitTests) hittable=\(hittable)"
    }
}

extension KeyboardReadiness {
    @MainActor
    static func observeInput<Key>(
        _ keys: [Key],
        exists: (Key) -> Bool,
        frame: (Key) -> CGRect,
        isHittable: (Key) -> Bool
    ) -> KeyboardInputObservation {
        var examined = 0, existing = 0, hitTests = 0, hittable = 0
        let state = observe(keys, exists: { key in
            examined += 1
            let present = exists(key)
            if present { existing += 1 }
            return present
        }, frame: frame, isHittable: { key in
            hitTests += 1
            let reachable = isHittable(key)
            if reachable { hittable += 1 }
            return reachable
        })
        // Existing keys excluded before the actual hit test have invalid
        // geometry. Do not reread a frame or duplicate the geometry predicate.
        return KeyboardInputObservation(state: state, keys: keys.count, examined: examined,
            existing: existing, invalidGeometry: existing - hitTests, hitTests: hitTests, hittable: hittable)
    }
}
