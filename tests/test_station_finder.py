from freyja.station_finder import StationFinder


class Client:
    def stations_near(self, coordinates, **kwargs):
        assert coordinates == (1.0, 2.0, 3.0)
        assert kwargs["require_market"] is False
        return (
            {"system_name": "A", "name": "Small", "distance": 1,
             "distance_to_arrival": 10, "has_large_pad": False},
            {"system_name": "B", "name": "Planet", "distance": 2,
             "distance_to_arrival": 5, "has_large_pad": True,
             "is_planetary": True},
            {"system_name": "C", "name": "Orbital", "distance": 3,
             "distance_to_arrival": 100, "has_large_pad": True},
        )


def test_nearest_filters_for_large_ship_and_planetary_preference():
    result = StationFinder(Client()).nearest(
        (1.0, 2.0, 3.0), requires_large_pad=True,
        allow_planetary=False, limit=3,
    )
    assert len(result) == 1
    assert result[0]["station"] == "Orbital"
    assert result[0]["large_pad"] is True


def test_in_system_returns_all_matching_stations_in_arrival_order():
    result = StationFinder(Client()).in_system(
        (1.0, 2.0, 3.0), "B", allow_planetary=True
    )
    assert [item["station"] for item in result] == ["Planet"]
