import json
import pytest
from unittest.mock import MagicMock
from breba_app.filesystem.versioned_r2 import VersionedR2FileSystem, FileWrite, NotFound


@pytest.fixture
def mock_s3():
    """Mocked boto3 client with in-memory storage."""
    storage = {}
    client = MagicMock()

    def put_object(Bucket, Key, Body, **kwargs):
        storage[(Bucket, Key)] = Body
        return {}

    def get_object(Bucket, Key):
        if (Bucket, Key) not in storage:
            raise client.exceptions.NoSuchKey({})
        return {"Body": MagicMock(read=lambda: storage[(Bucket, Key)])}

    def head_object(Bucket, Key):
        if (Bucket, Key) not in storage:
            from botocore.exceptions import ClientError
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}}, "head_object"
            )
        return {}

    client.put_object.side_effect = put_object
    client.get_object.side_effect = get_object
    client.head_object.side_effect = head_object
    client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
    client._storage = storage
    return client


@pytest.fixture
def fs(mock_s3):
    return VersionedR2FileSystem(
        bucket_name="test-bucket",
        endpoint_url="https://fake.endpoint",
        user_name="alice",
        session_id="s1",
        s3_client=mock_s3,
    )


def test_init_and_version_zero(fs, mock_s3):
    # Should create version 0
    v = fs.get_version()
    assert v == 0
    assert any("0.json" in k[1] for k in mock_s3._storage.keys())


def test_write_and_read(fs):
    v1 = fs.write_file("app/main.txt", "hello world")
    assert v1 == 1
    content = fs.read_text("app/main.txt")
    assert content == "hello world"


def test_deduplication(fs):
    fs.write_file("a.txt", "one")
    v2 = fs.write_file("a.txt", "one")  # identical
    assert v2 == 2  # version incremented
    manifest2 = fs._get_manifest(2)
    manifest1 = fs._get_manifest(1)
    # sha256 identical; same key reused
    assert manifest1["files"]["a.txt"]["sha256"] == manifest2["files"]["a.txt"]["sha256"]


def test_file_exists(fs):
    fs.write_file("foo/bar.txt", "hi")
    assert fs.file_exists("foo/bar.txt")
    assert not fs.file_exists("missing.txt")


def test_invalid_paths_rejected(fs):
    with pytest.raises(ValueError):
        fs.write_file("../secret.txt", "oops")
    with pytest.raises(ValueError):
        fs.write_file("foo/..", "oops")
    with pytest.raises(ValueError):
        fs.write_file("foo/\x00bad.txt", "oops")


def test_object_exists_strict_error(fs, mock_s3):
    # non-404 should propagate
    from botocore.exceptions import ClientError

    def bad_head(Bucket, Key):
        raise ClientError({"Error": {"Code": "500"}}, "head_object")

    mock_s3.head_object.side_effect = bad_head
    with pytest.raises(ClientError):
        fs._object_exists("whatever")


def test_repr_no_network(fs, mock_s3):
    fs_repr = repr(fs)
    assert "VersionedR2FileSystem" in fs_repr
    # ensure no s3.get_object() was called
    assert mock_s3.get_object.call_count == 0


def test_notfound_on_missing_manifest(fs):
    with pytest.raises(NotFound):
        fs._get_manifest(99)


def test_batch_write_atomic(fs, mock_s3):
    fs.write_file("ok.txt", "1")  # creates version 1

    def fail_put_object(Bucket, Key, Body, **kw):
        if "bad.txt" in Key:
            raise Exception("simulated failure")
        mock_s3._storage[(Bucket, Key)] = Body

    mock_s3.put_object.side_effect = fail_put_object

    with pytest.raises(Exception):
        fs.batch_write([
            FileWrite(path="ok.txt", content="ok"),
            FileWrite(path="bad.txt", content="fail"),
        ])

    # Ensure pointer still at old version (1)
    assert fs.get_version() == 1
