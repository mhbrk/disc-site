from collections import defaultdict
from unittest.mock import Mock, patch

from common.storage import list_files_structured, register_file, make_dir_tree


class MockBlob:
    def __init__(self, name, metadata=None):
        self.name = name
        self.metadata = metadata or {}


def test_register_file():
    """Test the register_file helper function"""
    directory = make_dir_tree()
    parts = ["images", "folder1", "test.png"]

    result = register_file(parts, directory)

    assert "images" in directory
    assert "folder1" in directory["images"]
    assert result is directory["images"]["folder1"]


def test_list_files_structured_empty():
    """Test with no files"""
    with patch('google.cloud.storage.Client') as mock_client:
        # Setup mock bucket and blobs
        mock_bucket = Mock()
        mock_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.list_blobs.return_value = []

        result = list_files_structured("test_session")
        assert result == {}


def test_list_files_structured_single_file():
    """Test with a single file"""
    with patch('google.cloud.storage.Client'):
        # Setup mock bucket
        mock_bucket = Mock()
        mock_blob = MockBlob(
            "test_session/images/test.png",
            {"description": "A test image"}
        )
        mock_bucket.list_blobs.return_value = [mock_blob]

        # Patch the private_bucket in the storage module
        with patch('common.storage.private_bucket', mock_bucket):
            result = list_files_structured("test_session")

        expected = defaultdict(dict, {
            "images": defaultdict(dict, {
                "test.png": {"__description__": "A test image"}
            })
        })
        assert result == expected


def test_list_files_structured_nested():
    """Test with nested directory structure"""
    with patch('google.cloud.storage.Client'):
        # Setup mock bucket with multiple blobs
        mock_bucket = Mock()
        mock_blobs = [
            MockBlob("test_session/images/folder1/test1.png", {"description": "Image 1"}),
            MockBlob("test_session/images/folder1/test2.png", {"description": "Image 2"}),
            MockBlob("test_session/images/folder2/test3.png", {"description": "Image 3"}),
        ]
        mock_bucket.list_blobs.return_value = mock_blobs

        with patch('common.storage.private_bucket', mock_bucket):
            result = list_files_structured("test_session")

        expected = defaultdict(dict, {
            "images": defaultdict(dict, {
                "folder1": defaultdict(dict, {
                    "test1.png": {"__description__": "Image 1"},
                    "test2.png": {"__description__": "Image 2"}
                }),
                "folder2": defaultdict(dict, {
                    "test3.png": {"__description__": "Image 3"}
                })
            })
        })
        assert result == expected


def test_list_files_structured_no_metadata():
    """Test files without metadata"""
    with patch('google.cloud.storage.Client'):
        mock_bucket = Mock()
        mock_blob = MockBlob("test_session/images/no_meta.png")
        mock_bucket.list_blobs.return_value = [mock_blob]

        with patch('common.storage.private_bucket', mock_bucket):
            result = list_files_structured("test_session")

        expected = defaultdict(dict, {
            "images": defaultdict(dict, {
                "no_meta.png": {"__description__": "No description"}
            })
        })
        assert result == expected


def test_list_files_structured_multiple_sessions():
    """Test that files from different sessions are separated"""
    with patch('google.cloud.storage.Client'):
        mock_bucket = Mock()
        mock_blobs = [
            MockBlob("session1/images/test1.png", {"description": "Session 1"}),
            MockBlob("session2/images/test2.png", {"description": "Session 2"}),
        ]
        mock_bucket.list_blobs.return_value = mock_blobs

        with patch('common.storage.private_bucket', mock_bucket):
            result = list_files_structured("session1")

        # Assert list_blobs was called with the correct prefix
        mock_bucket.list_blobs.assert_called_once_with(prefix="session1")
