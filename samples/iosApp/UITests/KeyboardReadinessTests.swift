import XCTest

final class KeyboardReadinessTests: XCTestCase {
    private let visible = CGRect(x: 10, y: 200, width: 32, height: 40)

    @MainActor
    func testInvalidGeometryNeverInvokesHittabilityOrProvesDismissal() {
        let invalid = [
            CGRect(x: CGFloat.infinity, y: CGFloat.infinity, width: 0, height: 0),
            CGRect.null, CGRect.infinite, CGRect.zero,
            CGRect(x: CGFloat.nan, y: 200, width: 32, height: 40),
            CGRect(x: 10, y: CGFloat.nan, width: 32, height: 40),
            CGRect(x: 10, y: 200, width: CGFloat.nan, height: 40),
            CGRect(x: 10, y: 200, width: 32, height: CGFloat.infinity),
            CGRect(x: 10, y: 200, width: 0, height: 40),
            CGRect(x: 10, y: 200, width: 32, height: -1),
            CGRect(x: CGFloat.greatestFiniteMagnitude, y: 0,
                   width: CGFloat.greatestFiniteMagnitude, height: 40)
        ]
        for (index, bounds) in invalid.enumerated() {
            let result = KeyboardReadiness.observe([bounds], exists: { _ in true }, frame: { $0 }) { _ in
                XCTFail("Invalid geometry must not enter XCTest's hit-target calculation")
                return true
            }
            XCTAssertEqual(result, .indeterminate, "Invalid geometry case \(index)")
            XCTAssertNotEqual(result, .hittable)
            XCTAssertNotEqual(result, .notHittable)
        }
    }

    @MainActor
    func testValidGeometryStillRequiresActualHittability() {
        var calls = 0
        let result = KeyboardReadiness.observe([visible], exists: { _ in true }, frame: { $0 }) { _ in
            calls += 1
            return false
        }
        XCTAssertEqual(calls, 1)
        XCTAssertEqual(result, .notHittable)
    }

    @MainActor
    func testActuallyHittableKeyProvesReadiness() {
        var calls = 0
        let result = KeyboardReadiness.observe([visible], exists: { _ in true }, frame: { $0 }) { _ in
            calls += 1
            return true
        }
        XCTAssertEqual(calls, 1)
        XCTAssertEqual(result, .hittable)
    }

    @MainActor
    func testRemovedKeysNeverReadGeometryOrHittability() {
        let result = KeyboardReadiness.observe([0], exists: { _ in false }, frame: { _ in
            XCTFail("A removed key has no current geometry")
            return self.visible
        }, isHittable: { _ in
            XCTFail("A removed key must not be hit-tested")
            return true
        })
        XCTAssertEqual(result, .notHittable)
    }

    @MainActor
    func testEmptyKeyInventoryIsNotHittable() {
        let result = KeyboardReadiness.observe([CGRect](), exists: { _ in
            XCTFail("Empty inventory must not probe an element")
            return true
        }, frame: { $0 }, isHittable: { _ in
            XCTFail("Empty inventory must not hit-test an element")
            return true
        })
        XCTAssertEqual(result, .notHittable)
    }

    @MainActor
    func testUnknownKeyPreventsDismissalWithOtherNonhittableKeys() {
        for bounds in [[CGRect.null, visible], [visible, CGRect.null]] {
            var calls = 0
            let result = KeyboardReadiness.observe(bounds, exists: { _ in true }, frame: { $0 }) { key in
                XCTAssertEqual(key, self.visible)
                calls += 1
                return false
            }
            XCTAssertEqual(calls, 1)
            XCTAssertEqual(result, .indeterminate)
        }
    }

    @MainActor
    func testActualHittableKeyWinsRegardlessOfUnknownKeyOrder() {
        for bounds in [[CGRect.null, visible], [visible, CGRect.null]] {
            var calls = 0
            let result = KeyboardReadiness.observe(bounds, exists: { _ in true }, frame: { $0 }) { key in
                XCTAssertEqual(key, self.visible)
                calls += 1
                return true
            }
            XCTAssertEqual(calls, 1)
            XCTAssertEqual(result, .hittable)
        }
    }

    @MainActor
    func testTransitioningGeometryIsNeitherReadinessNorDismissal() {
        let frames = [CGRect.null, visible, CGRect.null, visible]
        let hitResults = [false, true, false, false]
        var actualHitTests = 0
        let states = frames.indices.map { index in
            KeyboardReadiness.observe([frames[index]], exists: { _ in true }, frame: { $0 }) { _ in
                actualHitTests += 1
                return hitResults[index]
            }
        }
        XCTAssertEqual(states, [.indeterminate, .hittable, .indeterminate, .notHittable])
        XCTAssertEqual(actualHitTests, 2)
    }
}
