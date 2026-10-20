from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'data-pipeline'))

import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from metadata_cleaner import clean_metadata, locations, point, read_run

RUN="00000000-0000-0000-0000-000000000001"
AT="2026-09-30T12:00:00+00:00"


class MetadataTests(unittest.TestCase):
    def test_svy21_origin_and_axis_order(self):
        result=point(28001.642,38744.572,"EPSG:3414")
        self.assertAlmostEqual(result["latitude"],1.366666667,places=6)
        self.assertAlmostEqual(result["longitude"],103.833333333,places=6)
        self.assertEqual(point(1.29375,103.85718,"EPSG:4326"),
                         {"latitude":1.29375,"longitude":103.85718})
        for x,y in [(103.85718,1.29375),(0,0),(float("nan"),103.8)]:
            with self.assertRaises(ValueError):
                point(x,y,"EPSG:4326")

    def test_multiple_ura_points_survive_and_not_called_entrance(self):
        raw={"ppCode":"A0004","vehCat":"Car","ppName":"Street","parkCapacity":69,
             "geometries":[{"coordinates":"31063.017,31665.0933"},
                           {"coordinates":"31083.017,31675.0933"}]}
        rows,rejected=clean_metadata([raw,raw],"ura_details",RUN,AT)
        self.assertFalse(rejected)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["car_capacity"],69)  # NOT 138 for two tariff rows
        self.assertEqual(len(rows[0]["location_points"]),2)
        self.assertIsNone(rows[0]["latitude"])
        self.assertEqual(rows[0]["location_status"],"multiple_points")

    def test_conflicting_capacity_does_not_destroy_good_location(self):
        raw={"ppCode":"A0004","vehCat":"Car","ppName":"Street","parkCapacity":69,
             "geometries":[{"coordinates":"31063.017,31665.0933"}]}
        rows,_=clean_metadata([raw,{**raw,"parkCapacity":70}],"ura_details",RUN,AT)
        self.assertIsNone(rows[0]["car_capacity"])
        self.assertEqual(rows[0]["location_status"],"single_point")
        self.assertIn("capacity_requires_review",rows[0]["quality_flags"])

    def test_partial_geometry_is_quarantined(self):
        points,status,flags,_=locations({"geometries":[{"coordinates":"31063.017,31665.0933"},
                                                     {"coordinates":"invalid"}]},"ura_direct")
        self.assertEqual(points,[])
        self.assertEqual(status,"invalid")
        self.assertIn("invalid_geometry",flags)

    def test_vehicles_and_agencies_not_combined(self):
        raws=[{"Agency":a,"CarParkID":"1","LotType":"C","Location":"1.29375 103.85718"}
              for a in ["HDB","LTA"]]
        rows,_=clean_metadata(raws,"lta_datamall",RUN,AT)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r["car_capacity"] is None for r in rows))
        rows,_=clean_metadata([{"ppCode":"A0004","vehCat":"Motorcycle","parkCapacity":50}],"ura_details",RUN,AT)
        self.assertEqual(rows,[])

    def test_archive_tampering_fails_before_cleaning(self):
        with TemporaryDirectory() as folder:
            directory=Path(folder)
            raw=b'{"value":[]}'
            (directory/"lta-0.json.gz").write_bytes(gzip.compress(raw))
            manifest={"status":"collected","raw":[{"file":"lta-0.json.gz","sha256":hashlib.sha256(raw).hexdigest()}]}
            (directory/"manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(len(read_run(directory)[1]),1)
            (directory/"lta-0.json.gz").write_bytes(gzip.compress(b'{}'))
            with self.assertRaisesRegex(ValueError,"checksum"):
                read_run(directory)


if __name__=="__main__":
    unittest.main()
