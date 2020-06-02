import pytest

import common
import sync


class TestSync:
    @pytest.fixture(autouse=True)
    def monkeypatch_clients(self, monkeypatch, mock_ddb_table, mock_box_client):
        monkeypatch.setattr(common, "get_ddb_table", lambda: mock_ddb_table)
        monkeypatch.setattr(common, "get_box_client", lambda: (mock_box_client, "some-webhook-key"))

    def test_sync_empty(self, ddb_items):
        sync.lambda_handler({}, None)
        assert len(ddb_items) == 0

    def test_sync(
        self,
        ddb_items,
        create_folder,
        create_file,
        create_shared_file,
        create_shared_folder,
        managed_folder,
        create_shared_link,
        mock_box_client,
    ):
        # supposed to exist after sync
        correct_file = create_shared_file()
        ddb_items.append(common.make_ddb_item(correct_file))

        # supposed to exist after sync
        missing_file = create_shared_file()

        # not supposed to exist after sync
        no_longer_shared_file = create_file(parent_folder=managed_folder)
        ddb_items.append(
            {
                "filepath": common.get_filepath(no_longer_shared_file),
                "box_file_id": no_longer_shared_file.id,
                "download_url": "some-bogus-download-url",
            }
        )

        # not supposed to exist after sync
        ddb_items.append(
            {
                "filepath": "some/deleted/file.dat",
                "box_file_id": "123456789",
                "download_url": "some-other-bogus-download-url",
            }
        )

        # file in a shared folder that's missing from ddb
        # supposed to exist after sync
        shared_folder = create_shared_folder(parent_folder=managed_folder)
        unshared_file = create_file(parent_folder=shared_folder)

        sync.lambda_handler({}, None)

        # 5 files, 3 should exist, 2 should not
        assert len(ddb_items) == 3
        file_ids = {i["box_file_id"] for i in ddb_items}
        assert file_ids == {correct_file.id, missing_file.id, unshared_file.id}

    def test_sync_ddb_paging(self, ddb_items):
        for i in range(5 * 2 + 1):
            ddb_items.append(
                {
                    "filepath": f"some/defunct/file-{i}.dat",
                    "box_file_id": f"123456{i}",
                    "download_url": f"some-defunct-download-url-{i}",
                }
            )

        sync.lambda_handler({}, None)

        assert len(ddb_items) == 0
