from __future__ import annotations

import pytest

from chip_archive_codec import (
    ChipArchiveError,
    decode_chip_branch_archive,
    encode_chip_branch_archive,
    find_archived_branch_payload,
)


def sample_rows():
    return [
        {
            "id": 2,
            "ticker": "2330.TW",
            "branch_payload_json": '{"branches":[{"name":"A","net":12}]}',
        },
        {
            "id": 1,
            "ticker": "2317.TW",
            "branch_payload_json": '{"branches":[{"name":"B","net":-3}]}',
        },
    ]


def test_chip_archive_round_trip_is_deterministic_and_checksum_verified():
    first = encode_chip_branch_archive(sample_rows())
    second = encode_chip_branch_archive(reversed(sample_rows()))

    assert first == second
    restored = decode_chip_branch_archive(
        first["payload_blob"],
        expected_sha256=first["payload_sha256"],
        expected_row_count=2,
    )
    assert [item["id"] for item in restored] == [1, 2]
    archive_row = {
        "payload_blob": first["payload_blob"],
        "payload_sha256": first["payload_sha256"],
        "source_row_count": 2,
    }
    assert find_archived_branch_payload(archive_row, "2330.TW") == {
        "branches": [{"name": "A", "net": 12}]
    }


def test_chip_archive_rejects_checksum_and_row_count_mismatch():
    archive = encode_chip_branch_archive(sample_rows())

    with pytest.raises(ChipArchiveError, match="checksum mismatch"):
        decode_chip_branch_archive(
            archive["payload_blob"],
            expected_sha256="0" * 64,
        )
    with pytest.raises(ChipArchiveError, match="row count mismatch"):
        decode_chip_branch_archive(
            archive["payload_blob"],
            expected_row_count=3,
        )


def test_chip_archive_rejects_invalid_source_rows():
    with pytest.raises(ChipArchiveError, match="positive id and ticker"):
        encode_chip_branch_archive([{"id": 0, "ticker": "", "branch_payload": {}}])
