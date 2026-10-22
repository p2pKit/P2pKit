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

    @MainActor
    func testInputCountersReuseOriginalGuardsWithoutExtraQueries() {
        var existenceCalls = 0, frameCalls = 0, hitCalls = 0
        let observation = KeyboardReadiness.observeInput([0, 1, 2, 3, 4], exists: { key in
            existenceCalls += 1
            return key != 0
        }, frame: { key in
            frameCalls += 1
            return key == 1 ? CGRect.null : self.visible
        }, isHittable: { key in
            hitCalls += 1
            return key == 3
        })
        XCTAssertEqual(observation, KeyboardInputObservation(state: .hittable, keys: 5,
            examined: 4, existing: 3, invalidGeometry: 1, hitTests: 2, hittable: 1))
        XCTAssertEqual(existenceCalls, 4)
        XCTAssertEqual(frameCalls, 3)
        XCTAssertEqual(hitCalls, 2)
        XCTAssertEqual(observation.diagnostic,
            "state=HITTABLE keys=5 examined=4 existing=3 invalidGeometry=1 hitTests=2 hittable=1")
    }

    @MainActor
    func testInputUnknownAndNonhittableKeysNeverProduceReadiness() {
        for frames in [[CGRect.null, visible], [visible, CGRect.null]] {
            let observation = KeyboardReadiness.observeInput(frames, exists: { _ in true }, frame: { $0 }) { _ in false }
            XCTAssertEqual(observation, KeyboardInputObservation(state: .indeterminate, keys: 2,
                examined: 2, existing: 2, invalidGeometry: 1, hitTests: 1, hittable: 0))
            XCTAssertTrue(observation.diagnostic.hasPrefix("state=INDETERMINATE "))
        }
        let observation = KeyboardReadiness.observeInput([visible], exists: { _ in true }, frame: { $0 }) { _ in false }
        XCTAssertEqual(observation.state, .notHittable)
        XCTAssertEqual(observation.hitTests, 1)
        XCTAssertEqual(observation.hittable, 0)
    }

    @MainActor
    func testInputRemovedOrEmptyInventoryDoesNotReadFramesOrHitTests() {
        for keys in [[0, 1], []] {
            let observation = KeyboardReadiness.observeInput(keys, exists: { _ in false }, frame: { _ in
                XCTFail("Removed keys must not acquire geometry")
                return self.visible
            }, isHittable: { _ in
                XCTFail("Removed keys must not enter hit testing")
                return true
            })
            XCTAssertEqual(observation, KeyboardInputObservation(state: .notHittable, keys: keys.count,
                examined: keys.count, existing: 0, invalidGeometry: 0, hitTests: 0, hittable: 0))
        }
    }

    @MainActor
    func testInputObservationDoesNotReusePriorSuccessfulKeyOrCounters() {
        let first = KeyboardReadiness.observeInput([visible], exists: { _ in true }, frame: { $0 }) { _ in true }
        let second = KeyboardReadiness.observeInput([CGRect.null], exists: { _ in true }, frame: { $0 }) { _ in
            XCTFail("A subsequent invalid key must not reuse prior hittability")
            return true
        }
        XCTAssertEqual(first.state, .hittable)
        XCTAssertEqual(second, KeyboardInputObservation(state: .indeterminate, keys: 1,
            examined: 1, existing: 1, invalidGeometry: 1, hitTests: 0, hittable: 0))
        XCTAssertFalse(second.diagnostic.contains("HITTABLE "))
    }

}
