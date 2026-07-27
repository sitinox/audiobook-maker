import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import audiobook_maker.pipeline as pipeline
from audiobook_maker.common import Settings
from audiobook_maker.m4b import M4BChapter
from audiobook_maker.pipeline import PreparedTrack, TrackConversionResult


def prepared_track(number: int) -> PreparedTrack:
    return PreparedTrack(
        display_number=str(number).zfill(3),
        track_number=number,
        base_heading=f"Chapter {number}",
        text_file=Path(f"chapter-{number}.txt"),
        mp3_file=Path(f"chapter-{number}.mp3"),
        existing_mp3_file=None,
        spoken_text=f"Chapter {number}",
        word_total=number,
    )


def result_for(track: PreparedTrack) -> TrackConversionResult:
    return TrackConversionResult(
        chapter=M4BChapter(
            title=track.base_heading,
            audio_path=track.mp3_file,
        ),
        duration=float(track.track_number),
        report_lines=(f"Finished {track.track_number}",),
    )


def test_worker_count_uses_available_cores_and_never_exceeds_tracks(monkeypatch):
    monkeypatch.setattr(pipeline.os, "cpu_count", lambda: 8)

    assert pipeline._conversion_worker_count(None, 20) == 8
    assert pipeline._conversion_worker_count(None, 3) == 3
    assert pipeline._conversion_worker_count(4, 20) == 4
    assert pipeline._conversion_worker_count(20, 3) == 3
    assert pipeline._conversion_worker_count(None, 0) == 1


def test_worker_count_rejects_non_positive_values():
    with pytest.raises(ValueError, match="at least 1"):
        pipeline._conversion_worker_count(0, 3)


def test_parallel_track_conversion_runs_concurrently_and_preserves_order(
    tmp_path,
    monkeypatch,
):
    tracks = [prepared_track(number) for number in range(1, 4)]
    all_workers_started = threading.Barrier(3)
    completed_order = []
    completed_lock = threading.Lock()

    def convert(track, **_kwargs):
        all_workers_started.wait(timeout=2)
        with completed_lock:
            completed_order.append(track.track_number)
        return result_for(track)

    monkeypatch.setattr(pipeline, "_convert_prepared_track", convert)
    monkeypatch.setattr(pipeline, "say", lambda _message: None)

    results = pipeline._convert_tracks(
        tracks,
        book=SimpleNamespace(),
        settings=Settings(),
        force=False,
        temp_dir=tmp_path,
        jobs=3,
    )

    assert sorted(completed_order) == [1, 2, 3]
    assert [result.chapter.title for result in results] == [
        "Chapter 1",
        "Chapter 2",
        "Chapter 3",
    ]


def test_single_worker_uses_serial_path(tmp_path, monkeypatch):
    tracks = [prepared_track(number) for number in range(1, 4)]
    calls = []

    def convert(track, **_kwargs):
        calls.append(track.track_number)
        return result_for(track)

    monkeypatch.setattr(pipeline, "_convert_prepared_track", convert)
    monkeypatch.setattr(pipeline, "say", lambda _message: None)

    results = pipeline._convert_tracks(
        tracks,
        book=SimpleNamespace(),
        settings=Settings(),
        force=False,
        temp_dir=tmp_path,
        jobs=1,
    )

    assert calls == [1, 2, 3]
    assert [result.duration for result in results] == [1.0, 2.0, 3.0]


def test_parallel_path_starts_longest_tracks_first(tmp_path, monkeypatch):
    tracks = [prepared_track(number) for number in range(1, 5)]
    first_workers_started = threading.Barrier(2)
    started = []
    started_lock = threading.Lock()

    def convert(track, **_kwargs):
        with started_lock:
            started.append(track.track_number)
            position = len(started)
        if position <= 2:
            first_workers_started.wait(timeout=2)
        return result_for(track)

    monkeypatch.setattr(pipeline, "_convert_prepared_track", convert)
    monkeypatch.setattr(pipeline, "say", lambda _message: None)

    results = pipeline._convert_tracks(
        tracks,
        book=SimpleNamespace(),
        settings=Settings(),
        force=False,
        temp_dir=tmp_path,
        jobs=2,
    )

    assert set(started[:2]) == {3, 4}
    assert [result.chapter.title for result in results] == [
        "Chapter 1",
        "Chapter 2",
        "Chapter 3",
        "Chapter 4",
    ]
