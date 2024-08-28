import numpy as np
import pytest

from evaluation.plotting import (
    plot_bar_charts,
    plot_box_chart,
    plot_box_charts_grid,
    plot_radar_chart,
    plot_red_teaming_table,
)


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Fixture for temporary output directory."""
    return tmp_path / "output"


def test_plot_bar_charts(tmp_output_dir):
    data = {
        "Model1": [
            {
                "Metric 1": 1,
                "Metric 2": 2,
                "Metric 3": 2,
            },
            {
                "Metric 1": 0.5,
                "Metric 2": 1.0,
                "Metric 3": 1.0,
            },
            {"Metric 1": np.float64(3.0), "Metric 2": np.float64(5.0), "Metric 3": np.float64(5.0)},
        ],
        "Model2": [
            {
                "Metric 1": 1,
                "Metric 2": 2,
                "Metric 3": 2,
            },
            {
                "Metric 1": 0.5,
                "Metric 2": 1.0,
                "Metric 3": 1.0,
            },
            {"Metric 1": np.float64(3.0), "Metric 2": np.float64(3.0), "Metric 3": np.float64(4.0)},
        ],
    }
    layout = (1, 3)
    titles = ["Title 1", "Title 2", "Title 3"]
    y_labels = ["l1", "l2", "l3"]
    y_max_lim = [2, 1.0, 5.0]

    output_path = tmp_output_dir / "bar_chart.png"

    plot_bar_charts(layout, data, titles, y_labels, output_path, y_max_lim=y_max_lim)

    # Ensure the output file was created
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_box_charts_grid(tmp_output_dir):
    data = {
        "Metric 1": [[0.8, 0.6, 0.7], [0.9, 0.7, 0.8]],
        "Metric 2": [[0.5, 0.6, 0.4], [0.7, 0.8, 0.6]],
    }
    layout = (1, 2)
    titles = ["Metric 1", "Metric 2"]
    y_labels = ["Score", "Score"]

    output_path = tmp_output_dir / "box_chart_grid.png"

    plot_box_charts_grid(layout, data, titles, y_labels, output_path)

    # Ensure the output file was created
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_box_chart(tmp_output_dir):
    data = {
        "Model A": [[0.8, 0.6, 0.7], [0.9, 0.7, 0.8]],
        "Model B": [[0.5, 0.6, 0.4], [0.7, 0.8, 0.6]],
    }
    x_labels = ["Metric 1", "Metric 2"]
    y_label = "Score"
    title = "Box Chart"

    output_path = tmp_output_dir / "box_chart.png"

    plot_box_chart(data, title, x_labels, y_label, output_path)

    # Ensure the output file was created
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_radar_chart(tmp_output_dir):
    metric_label_list = ["Metric 1", "Metric 2", "Metric 3"]
    data = {
        "Model A": [0.8, 0.7, 0.6],
        "Model B": [0.7, 0.6, 0.5],
    }
    title = "Radar Chart"

    output_path = tmp_output_dir / "radar_chart.png"

    plot_radar_chart(metric_label_list, data, title, output_path, num=5)

    # Ensure the output file was created
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_red_teaming_table(tmp_output_dir):
    metric_label_list = ["Metric 1", "Metric 2", "Metric 3"]
    data = {
        "Model A": ["Pass", "Fail", "Pass"],
        "Model B": ["Fail", "Pass", "Fail"],
    }

    output_path = tmp_output_dir / "red_teaming_table.png"

    plot_red_teaming_table(metric_label_list, data, output_path)

    # Ensure the output file was created
    assert output_path.exists()
    assert output_path.stat().st_size > 0
