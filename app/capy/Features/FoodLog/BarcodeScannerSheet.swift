import AVFoundation
import SwiftUI
import VisionKit

/// FoodNoms-style barcode scanner: VisionKit DataScanner → `lookup_barcode` → hit or miss.
struct BarcodeScannerSheet: View {
    let onHit: (BarcodeLookupHit) -> Void
    let onMissSearch: () -> Void
    let onMissCustom: () -> Void

    @Environment(\.dismiss) private var dismiss

    @State private var phase: Phase = .checking
    @State private var statusMessage = "Point at a barcode"
    @State private var lastCode: String?
    @State private var lookupTask: Task<Void, Never>?
    @State private var showMissAlert = false
    @State private var errorMessage: String?

    private enum Phase: Equatable {
        case checking
        case needsPermission
        case unsupported
        case scanning
        case lookingUp
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                switch phase {
                case .checking:
                    ProgressView()
                        .tint(.white)
                case .needsPermission:
                    permissionView
                case .unsupported:
                    messageView(
                        title: "Scanner unavailable",
                        detail: "Barcode scanning needs a device with a supported camera."
                    )
                case .scanning, .lookingUp:
                    DataScannerRepresentable(
                        isPaused: phase == .lookingUp,
                        onCode: handleCode(_:)
                    )
                    .ignoresSafeArea()
                    overlayChrome
                }
            }
            .navigationTitle("Scan barcode")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        lookupTask?.cancel()
                        dismiss()
                    }
                    .foregroundStyle(.white)
                }
            }
            .toolbarBackground(.hidden, for: .navigationBar)
            .alert("No match", isPresented: $showMissAlert) {
                Button("Search") {
                    onMissSearch()
                    dismiss()
                }
                Button("Add custom food") {
                    onMissCustom()
                    dismiss()
                }
                Button("Scan again", role: .cancel) {
                    lastCode = nil
                    statusMessage = "Point at a barcode"
                    phase = .scanning
                    errorMessage = nil
                }
            } message: {
                Text("That barcode isn’t in Open Food Facts. Search the catalog or add a custom food.")
            }
            .task {
                await prepareScanner()
            }
            .onDisappear {
                lookupTask?.cancel()
            }
        }
    }

    private var overlayChrome: some View {
        VStack {
            Spacer()
            VStack(spacing: 10) {
                if phase == .lookingUp {
                    ProgressView()
                        .tint(.white)
                        .controlSize(.regular)
                        .transition(.opacity.combined(with: .scale))
                }
                Text(statusMessage)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                    .contentTransition(.opacity)
                if let errorMessage {
                    Text(errorMessage)
                        .font(.caption)
                        .foregroundStyle(Color.capy.accent)
                        .multilineTextAlignment(.center)
                        .transition(.opacity)
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity)
            .background(.ultraThinMaterial.opacity(0.9), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .padding(.horizontal, 16)
            .padding(.bottom, 28)
            .animation(.spring(response: 0.35, dampingFraction: 0.85), value: phase)
        }
    }

    private var permissionView: some View {
        messageView(
            title: "Camera access needed",
            detail: "Allow camera access in Settings so Capy can scan barcodes."
        ) {
            if let url = URL(string: UIApplication.openSettingsURLString) {
                Button("Open Settings") {
                    UIApplication.shared.open(url)
                }
                .buttonStyle(.borderedProminent)
                .tint(Color.capy.accent)
            }
        }
    }

    @ViewBuilder
    private func messageView(
        title: String,
        detail: String,
        @ViewBuilder extra: () -> some View = { EmptyView() }
    ) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "barcode.viewfinder")
                .font(.system(size: 44))
                .foregroundStyle(Color.capy.accent)
            Text(title)
                .font(.title3.weight(.semibold))
                .foregroundStyle(.white)
            Text(detail)
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.75))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
            extra()
        }
    }

    private func prepareScanner() async {
        guard DataScannerViewController.isSupported else {
            phase = .unsupported
            return
        }
        let status = AVCaptureDevice.authorizationStatus(for: .video)
        switch status {
        case .authorized:
            phase = DataScannerViewController.isAvailable ? .scanning : .unsupported
        case .notDetermined:
            let ok = await AVCaptureDevice.requestAccess(for: .video)
            if ok, DataScannerViewController.isAvailable {
                phase = .scanning
            } else if ok {
                phase = .unsupported
            } else {
                phase = .needsPermission
            }
        default:
            phase = .needsPermission
        }
    }

    private func handleCode(_ raw: String) {
        let digits = raw.filter(\.isNumber)
        guard digits.count >= 8 else { return }
        guard phase == .scanning else { return }
        guard digits != lastCode else { return }
        lastCode = digits
        withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
            phase = .lookingUp
            statusMessage = "Looking up…"
            errorMessage = nil
        }
        lookupTask?.cancel()
        lookupTask = Task { @MainActor in
            do {
                let response = try await AgentClient.shared.lookupBarcode(gtin: digits)
                guard !Task.isCancelled else { return }
                if let hit = response.hit {
                    onHit(hit)
                    dismiss()
                } else {
                    showMissAlert = true
                    phase = .scanning
                    statusMessage = "Point at a barcode"
                }
            } catch {
                guard !Task.isCancelled else { return }
                errorMessage = error.localizedDescription
                statusMessage = "Try again"
                phase = .scanning
                // Allow re-scan of the same code after a failure.
                lastCode = nil
            }
        }
    }
}

// MARK: - VisionKit bridge

private struct DataScannerRepresentable: UIViewControllerRepresentable {
    var isPaused: Bool
    var onCode: (String) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onCode: onCode)
    }

    func makeUIViewController(context: Context) -> DataScannerViewController {
        // Empty symbologies = all barcode types (UPC-A usually arrives as EAN-13).
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.barcode()],
            qualityLevel: .balanced,
            recognizesMultipleItems: false,
            isHighFrameRateTrackingEnabled: false,
            isPinchToZoomEnabled: true,
            isGuidanceEnabled: true,
            isHighlightingEnabled: true
        )
        scanner.delegate = context.coordinator
        context.coordinator.scanner = scanner
        try? scanner.startScanning()
        return scanner
    }

    func updateUIViewController(_ controller: DataScannerViewController, context: Context) {
        context.coordinator.onCode = onCode
        if isPaused {
            if controller.isScanning {
                controller.stopScanning()
            }
        } else if !controller.isScanning {
            try? controller.startScanning()
        }
    }

    static func dismantleUIViewController(_ controller: DataScannerViewController, coordinator: Coordinator) {
        if controller.isScanning {
            controller.stopScanning()
        }
    }

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        var onCode: (String) -> Void
        weak var scanner: DataScannerViewController?

        init(onCode: @escaping (String) -> Void) {
            self.onCode = onCode
        }

        func dataScanner(
            _ dataScanner: DataScannerViewController,
            didAdd addedItems: [RecognizedItem],
            allItems: [RecognizedItem]
        ) {
            emit(from: addedItems)
        }

        func dataScanner(
            _ dataScanner: DataScannerViewController,
            didUpdate updatedItems: [RecognizedItem],
            allItems: [RecognizedItem]
        ) {
            emit(from: updatedItems)
        }

        private func emit(from items: [RecognizedItem]) {
            for item in items {
                if case .barcode(let barcode) = item, let payload = barcode.payloadStringValue {
                    onCode(payload)
                    return
                }
            }
        }
    }
}
