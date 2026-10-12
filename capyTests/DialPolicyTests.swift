import XCTest
@testable import capy

final class DialPolicyTests: XCTestCase {
    func testQuietZeroUnprompted() {
        let m = DialPolicy.matrix(for: .quiet)
        XCTAssertFalse(m.unprompted)
        XCTAssertFalse(m.eveningCheckIn)
        XCTAssertFalse(m.benefitAfterLog)
        XCTAssertTrue(m.reactive)
    }

    func testGuidedEveningOnly() {
        let m = DialPolicy.matrix(for: .guided)
        XCTAssertTrue(m.unprompted)
        XCTAssertTrue(m.eveningCheckIn)
        XCTAssertFalse(m.benefitAfterLog)
        XCTAssertTrue(m.reactive)
    }

    func testFullAssistBenefitAfterLog() {
        let m = DialPolicy.matrix(for: .fullAssist)
        XCTAssertTrue(m.unprompted)
        XCTAssertTrue(m.eveningCheckIn)
        XCTAssertTrue(m.benefitAfterLog)
        XCTAssertTrue(m.reactive)
    }
}
