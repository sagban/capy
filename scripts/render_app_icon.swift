#!/usr/bin/env swift
import AppKit

/// Face-only Capy mark — flat, cute, brand colors. Edit here; no image models.

let size = 1024

func color(_ hex: String, alpha: CGFloat = 1) -> NSColor {
    let h = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
    var int: UInt64 = 0
    Scanner(string: h).scanHexInt64(&int)
    return NSColor(
        srgbRed: CGFloat((int >> 16) & 0xFF) / 255,
        green: CGFloat((int >> 8) & 0xFF) / 255,
        blue: CGFloat(int & 0xFF) / 255,
        alpha: alpha
    )
}

let cream = color("F3EFE7")
let moss = color("1FA971")
let fur = color("A67C52")
let furDeep = color("7A5235")
let muzzle = color("E2C4A0")
let blush = color("F0A090")
let ink = color("3D2A1A")

let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: size,
    pixelsHigh: size,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
)!
rep.size = NSSize(width: size, height: size)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let ctx = NSGraphicsContext.current!.cgContext
let full = CGRect(x: 0, y: 0, width: size, height: size)

// Full-bleed cream (iOS masks to squircle)
ctx.setFillColor(cream.cgColor)
ctx.fill(full)

// Soft moss vignette ring behind face
ctx.setFillColor(moss.withAlphaComponent(0.18).cgColor)
ctx.fillEllipse(in: CGRect(x: 40, y: 40, width: 944, height: 944))

// —— FACE ONLY (large, centered) ——
let head = CGRect(x: 140, y: 160, width: 744, height: 620)
ctx.setFillColor(fur.cgColor)
ctx.fillEllipse(in: head)

// Ears (on top of head)
func ear(at x: CGFloat) {
    let outer = CGRect(x: x, y: 680, width: 150, height: 170)
    ctx.setFillColor(fur.cgColor)
    ctx.fillEllipse(in: outer)
    ctx.setFillColor(blush.cgColor)
    ctx.fillEllipse(in: outer.insetBy(dx: 38, dy: 42))
}
ear(at: 200)
ear(at: 674)

// Muzzle
let snout = CGRect(x: 280, y: 220, width: 464, height: 340)
ctx.setFillColor(muzzle.cgColor)
ctx.fillEllipse(in: snout)

// Happy open-ish eyes (dots + crescent lids) — cute, readable small
func eye(cx: CGFloat, cy: CGFloat) {
    // white
    ctx.setFillColor(NSColor.white.cgColor)
    ctx.fillEllipse(in: CGRect(x: cx - 42, y: cy - 36, width: 84, height: 72))
    // pupil
    ctx.setFillColor(ink.cgColor)
    ctx.fillEllipse(in: CGRect(x: cx - 22, y: cy - 20, width: 44, height: 44))
    // sparkle
    ctx.setFillColor(NSColor.white.cgColor)
    ctx.fillEllipse(in: CGRect(x: cx - 6, y: cy + 2, width: 16, height: 16))
}
eye(cx: 380, cy: 480)
eye(cx: 644, cy: 480)

// Blush
ctx.setFillColor(blush.cgColor)
ctx.fillEllipse(in: CGRect(x: 220, y: 360, width: 90, height: 50))
ctx.fillEllipse(in: CGRect(x: 714, y: 360, width: 90, height: 50))

// Nose
ctx.setFillColor(furDeep.cgColor)
ctx.fillEllipse(in: CGRect(x: 456, y: 360, width: 112, height: 78))

// Big smile
let smile = CGMutablePath()
smile.addArc(
    center: CGPoint(x: 512, y: 310),
    radius: 110,
    startAngle: .pi * 1.12,
    endAngle: .pi * 1.88,
    clockwise: false
)
ctx.setStrokeColor(ink.cgColor)
ctx.setLineWidth(22)
ctx.setLineCap(.round)
ctx.addPath(smile)
ctx.strokePath()

NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else {
    fputs("encode failed\n", stderr)
    exit(1)
}
let out = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "app/capy/Assets.xcassets/AppIcon.appiconset/AppIcon.png"
try png.write(to: URL(fileURLWithPath: out))
print("wrote \(out)")
