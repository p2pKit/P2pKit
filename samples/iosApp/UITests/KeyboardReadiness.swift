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
