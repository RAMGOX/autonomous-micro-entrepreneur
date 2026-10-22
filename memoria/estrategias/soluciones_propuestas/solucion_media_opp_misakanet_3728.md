# Solution: Comprehensive Answers for Linked Issues #3659 & #3660
- **Issue:** [Ikalus1988/MisakaNet #3728](https://github.com/Ikalus1988/MisakaNet/issues/3728)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## Part 1: Solution for #3659 (macOS Display Preview Repeated Stepping & Rollback Preservation)

### Architectural Pattern: Immutable Baseline Capture & Monotonic Deadline Envelope

When allowing a user to repeatedly step through display configurations (resolution, refresh rates, HDR modes, color profiles), the system must preserve:
1. **The Initial Baseline (`CGDisplayModeRef` / `io_service_t` state):** Captured strictly once at $T_0$ prior to any mode switch. Subsequent step operations must mutate only the candidate buffer, never overwriting the snapshot taken at entry.
2. **Monotonic Expiration (`mach_continuous_time` / `DispatchSourceTimer`):** Stepping between display modes must **not** reset the confirmation timeout back to 15 seconds on every tap, which would allow a runaway script or broken display to stall indefinitely. The confirmation deadline must be anchored monotonically to $T_0 + \Delta_{max}$ (e.g. 15.0 seconds).
3. **Failed Rollback Evidence:** If the rollback call (`CGDisplaySetDisplayMode`) fails or throws an IOKit error (e.g. `kIOReturnUnsupportedMode`), serialize the original mode dictionary, target candidate mode, and IOKit error code to `~/Library/Logs/DisplayReversionAudit.log` and trigger an emergency CoreGraphics safe-mode fallback (`CGRestorePermanentDisplayConfiguration()`).

```swift
final class DisplayPreviewSession {
    private let displayID: CGDirectDisplayID
    private let initialMode: CGDisplayMode
    private let deadlineMachTime: UInt64
    private var rollbackTimer: DispatchSourceTimer?

    init(displayID: CGDirectDisplayID, timeoutSeconds: Double = 15.0) throws {
        self.displayID = displayID
        guard let current = CGDisplayCopyDisplayMode(displayID) else {
            throw DisplayError.failedToCaptureBaseline
        }
        self.initialMode = current
        self.deadlineMachTime = mach_continuous_time() + UInt64(timeoutSeconds * 1_000_000_000)
        startMonotonicTimer()
    }

    func stepToMode(_ nextMode: CGDisplayMode) throws {
        // Monotonic check
        guard mach_continuous_time() < deadlineMachTime else {
            rollback()
            throw DisplayError.timeoutExpired
        }
        CGDisplaySetDisplayMode(displayID, nextMode, nil)
    }

    func rollback() {
        rollbackTimer?.cancel()
        let err = CGDisplaySetDisplayMode(displayID, initialMode, nil)
        if err != .success {
            recordReversionFailure(error: err, baseline: initialMode)
            CGRestorePermanentDisplayConfiguration()
        }
    }
}
```

---

## Part 2: Solution for #3660 (Destination-Adjacent Non-Activating Adjustment Panel)

### AppKit Design: `NSPanel` with `.nonactivatingPanel` & First Responder Delegation

To prevent an adjustment floating palette from stealing primary key/typing focus from the destination editor window while allowing intentional arrow/tab adjustments:

1. **Panel Style Mask:** Initialize `NSPanel` with `[.nonactivatingPanel, .utilityWindow, .hudWindow]`. Set `becomesKeyOnlyIfNeeded = true` and `hidesOnDeactivate = false`.
2. **Window Level:** Float at `.floatingWindow` or `.popUpMenu` level to remain visible above display transitions without triggering `NSApplication.activate()`.
3. **Keyboard Handling:** Overriding `keyDown(with:)` inside the panel's custom view allows arrow keys and Esc (cancel/rollback) to be processed by the adjustment controls without taking full keyboard focus away from the underlying document editor.
4. **Preserved Deadline Sync:** Bind the preview rollback countdown directly via a Combine publisher so user adjustments within the panel do not delay or corrupt the rollback deadline.

```swift
final class NonActivatingAdjustmentPanel: NSPanel {
    init(contentRect: NSRect) {
        super.init(
            contentRect: contentRect,
            styleMask: [.nonactivatingPanel, .utilityWindow, .titled, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        self.isFloatingPanel = true
        self.level = .floating
        self.becomesKeyOnlyIfNeeded = true
        self.collectionBehavior = [.canJoinAllSpaces, .transient]
    }

    override var canBecomeKey: Bool {
        return false // Never steals typing focus from main window
    }
}
```
