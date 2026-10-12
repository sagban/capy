#!/usr/bin/env python3
"""Add DebugLocal/ReleaseLocal/DebugProd/ReleaseProd + xcconfig wiring to capy.xcodeproj."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBX = ROOT / "capy.xcodeproj" / "project.pbxproj"


def nid() -> str:
    return uuid.uuid4().hex[:24].upper()


def main() -> None:
    text = PBX.read_text()
    if "DebugLocal" in text and "Local.xcconfig" in text:
        print("already configured")
        return

    ids = {k: nid() for k in [
        "shared_file", "local_file", "prod_file", "config_group",
        "proj_debug_local", "proj_release_local", "proj_debug_prod", "proj_release_prod",
        "app_debug_local", "app_release_local", "app_debug_prod", "app_release_prod",
        "tests_debug_local", "tests_release_local", "tests_debug_prod", "tests_release_prod",
        "ui_debug_local", "ui_release_local", "ui_debug_prod", "ui_release_prod",
    ]}

    file_refs = f"""
\t\t{ids['shared_file']} /* Shared.xcconfig */ = {{isa = PBXFileReference; lastKnownFileType = text.xcconfig; name = Shared.xcconfig; path = Config/Shared.xcconfig; sourceTree = SOURCE_ROOT; }};
\t\t{ids['local_file']} /* Local.xcconfig */ = {{isa = PBXFileReference; lastKnownFileType = text.xcconfig; name = Local.xcconfig; path = Config/Local.xcconfig; sourceTree = SOURCE_ROOT; }};
\t\t{ids['prod_file']} /* Prod.xcconfig */ = {{isa = PBXFileReference; lastKnownFileType = text.xcconfig; name = Prod.xcconfig; path = Config/Prod.xcconfig; sourceTree = SOURCE_ROOT; }};
"""
    text = text.replace("/* End PBXFileReference section */", file_refs + "/* End PBXFileReference section */")

    config_group = f"""
\t\t{ids['config_group']} /* Config */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{ids['shared_file']} /* Shared.xcconfig */,
\t\t\t\t{ids['local_file']} /* Local.xcconfig */,
\t\t\t\t{ids['prod_file']} /* Prod.xcconfig */,
\t\t\t);
\t\t\tname = Config;
\t\t\tpath = Config;
\t\t\tsourceTree = SOURCE_ROOT;
\t\t}};
"""
    text = text.replace("/* End PBXGroup section */", config_group + "/* End PBXGroup section */")
    text = text.replace(
        "\t\t\t\t4F26888D307C679400532B65 /* Products */,\n",
        f"\t\t\t\t4F26888D307C679400532B65 /* Products */,\n\t\t\t\t{ids['config_group']} /* Config */,\n",
        1,
    )

    def get_block(block_id: str) -> str:
        pat = rf"(\t\t{block_id} /\* [^*]+ \*/ = \{{\n\t\t\tisa = XCBuildConfiguration;.*?\n\t\t\}};)"
        m = re.search(pat, text, re.S)
        if not m:
            raise SystemExit(f"missing block {block_id}")
        return m.group(1)

    def rename_block(block: str, new_id: str, new_name: str) -> str:
        block = re.sub(r"^\t\t[A-F0-9]{24}", f"\t\t{new_id}", block, count=1)
        block = re.sub(r"/\* (Debug|Release) \*/", f"/* {new_name} */", block, count=1)
        block = re.sub(r"name = (Debug|Release);", f"name = {new_name};", block)
        return block

    def with_xcconfig(block: str, xc_id: str, xc_name: str) -> str:
        if "baseConfigurationReference" in block:
            return block
        return block.replace(
            "isa = XCBuildConfiguration;\n\t\t\tbuildSettings = {",
            f"isa = XCBuildConfiguration;\n\t\t\tbaseConfigurationReference = {xc_id} /* {xc_name} */;\n\t\t\tbuildSettings = {{",
        )

    proj_debug = get_block("4F2688AB307C679500532B65")
    proj_release = get_block("4F2688AC307C679500532B65")
    app_debug = get_block("4F2688AE307C679500532B65")
    app_release = get_block("4F2688AF307C679500532B65")
    tests_debug = get_block("4F2688B1307C679500532B65")
    tests_release = get_block("4F2688B2307C679500532B65")
    ui_debug = get_block("4F2688B4307C679500532B65")
    ui_release = get_block("4F2688B5307C679500532B65")

    new_blocks: list[str] = [
        rename_block(proj_debug, ids["proj_debug_local"], "DebugLocal"),
        rename_block(proj_release, ids["proj_release_local"], "ReleaseLocal"),
        rename_block(proj_debug, ids["proj_debug_prod"], "DebugProd"),
        rename_block(proj_release, ids["proj_release_prod"], "ReleaseProd"),
        with_xcconfig(rename_block(app_debug, ids["app_debug_local"], "DebugLocal"), ids["local_file"], "Local.xcconfig"),
        with_xcconfig(rename_block(app_release, ids["app_release_local"], "ReleaseLocal"), ids["local_file"], "Local.xcconfig"),
        with_xcconfig(rename_block(app_debug, ids["app_debug_prod"], "DebugProd"), ids["prod_file"], "Prod.xcconfig"),
        with_xcconfig(rename_block(app_release, ids["app_release_prod"], "ReleaseProd"), ids["prod_file"], "Prod.xcconfig"),
        with_xcconfig(rename_block(tests_debug, ids["tests_debug_local"], "DebugLocal"), ids["local_file"], "Local.xcconfig"),
        with_xcconfig(rename_block(tests_release, ids["tests_release_local"], "ReleaseLocal"), ids["local_file"], "Local.xcconfig"),
        with_xcconfig(rename_block(tests_debug, ids["tests_debug_prod"], "DebugProd"), ids["prod_file"], "Prod.xcconfig"),
        with_xcconfig(rename_block(tests_release, ids["tests_release_prod"], "ReleaseProd"), ids["prod_file"], "Prod.xcconfig"),
        with_xcconfig(rename_block(ui_debug, ids["ui_debug_local"], "DebugLocal"), ids["local_file"], "Local.xcconfig"),
        with_xcconfig(rename_block(ui_release, ids["ui_release_local"], "ReleaseLocal"), ids["local_file"], "Local.xcconfig"),
        with_xcconfig(rename_block(ui_debug, ids["ui_debug_prod"], "DebugProd"), ids["prod_file"], "Prod.xcconfig"),
        with_xcconfig(rename_block(ui_release, ids["ui_release_prod"], "ReleaseProd"), ids["prod_file"], "Prod.xcconfig"),
    ]

    text = text.replace(
        "/* End XCBuildConfiguration section */",
        "\n".join(new_blocks) + "\n/* End XCBuildConfiguration section */",
    )

    replacements = [
        (
            """\t\t4F268887307C679400532B65 /* Build configuration list for PBXProject "capy" */ = {
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t4F2688AB307C679500532B65 /* Debug */,
\t\t\t\t4F2688AC307C679500532B65 /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t};""",
            f"""\t\t4F268887307C679400532B65 /* Build configuration list for PBXProject "capy" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t4F2688AB307C679500532B65 /* Debug */,
\t\t\t\t4F2688AC307C679500532B65 /* Release */,
\t\t\t\t{ids['proj_debug_local']} /* DebugLocal */,
\t\t\t\t{ids['proj_release_local']} /* ReleaseLocal */,
\t\t\t\t{ids['proj_debug_prod']} /* DebugProd */,
\t\t\t\t{ids['proj_release_prod']} /* ReleaseProd */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};""",
        ),
        (
            """\t\t4F2688AD307C679500532B65 /* Build configuration list for PBXNativeTarget "capy" */ = {
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t4F2688AE307C679500532B65 /* Debug */,
\t\t\t\t4F2688AF307C679500532B65 /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t};""",
            f"""\t\t4F2688AD307C679500532B65 /* Build configuration list for PBXNativeTarget "capy" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t4F2688AE307C679500532B65 /* Debug */,
\t\t\t\t4F2688AF307C679500532B65 /* Release */,
\t\t\t\t{ids['app_debug_local']} /* DebugLocal */,
\t\t\t\t{ids['app_release_local']} /* ReleaseLocal */,
\t\t\t\t{ids['app_debug_prod']} /* DebugProd */,
\t\t\t\t{ids['app_release_prod']} /* ReleaseProd */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};""",
        ),
        (
            """\t\t4F2688B0307C679500532B65 /* Build configuration list for PBXNativeTarget "capyTests" */ = {
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t4F2688B1307C679500532B65 /* Debug */,
\t\t\t\t4F2688B2307C679500532B65 /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t};""",
            f"""\t\t4F2688B0307C679500532B65 /* Build configuration list for PBXNativeTarget "capyTests" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t4F2688B1307C679500532B65 /* Debug */,
\t\t\t\t4F2688B2307C679500532B65 /* Release */,
\t\t\t\t{ids['tests_debug_local']} /* DebugLocal */,
\t\t\t\t{ids['tests_release_local']} /* ReleaseLocal */,
\t\t\t\t{ids['tests_debug_prod']} /* DebugProd */,
\t\t\t\t{ids['tests_release_prod']} /* ReleaseProd */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};""",
        ),
        (
            """\t\t4F2688B3307C679500532B65 /* Build configuration list for PBXNativeTarget "capyUITests" */ = {
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t4F2688B4307C679500532B65 /* Debug */,
\t\t\t\t4F2688B5307C679500532B65 /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t};""",
            f"""\t\t4F2688B3307C679500532B65 /* Build configuration list for PBXNativeTarget "capyUITests" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t4F2688B4307C679500532B65 /* Debug */,
\t\t\t\t4F2688B5307C679500532B65 /* Release */,
\t\t\t\t{ids['ui_debug_local']} /* DebugLocal */,
\t\t\t\t{ids['ui_release_local']} /* ReleaseLocal */,
\t\t\t\t{ids['ui_debug_prod']} /* DebugProd */,
\t\t\t\t{ids['ui_release_prod']} /* ReleaseProd */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};""",
        ),
    ]

    for old, new in replacements:
        if old not in text:
            raise SystemExit("configuration list block not found exactly")
        text = text.replace(old, new)

    PBX.write_text(text)
    print("OK", ids["local_file"], ids["prod_file"])


if __name__ == "__main__":
    main()
