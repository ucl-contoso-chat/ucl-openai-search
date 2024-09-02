import { EvaluationMetric } from "./EvaluationMetric";

import styles from "./EvaluationMetric.module.css";

interface Props {
    metrics: { name: string; display_name: string; description: string; [otherProps: string]: unknown }[];
    selectedMetrics: {}[];
    setSelectedMetrics: (selectedMetrics: {}[]) => void;
}

export const EvaluationMetricList = ({ metrics, selectedMetrics, setSelectedMetrics }: Props) => {
    const handleMetricCheck = (metricName?: string, checked?: boolean) => {
        if (typeof metricName === "string") {
            var selectedMetricsArray = [...selectedMetrics];
            if (!!!checked) {
                selectedMetricsArray = [...selectedMetrics, metricName];
            } else {
                selectedMetricsArray.splice(selectedMetrics.indexOf(metricName), 1);
            }
            setSelectedMetrics(selectedMetricsArray);
        }
    };

    return (
        <div className={styles.evaluationMetricContainer}>
            {metrics.map((metric, i) => (
                <div key={i}>
                    <EvaluationMetric metric={metric} checked={selectedMetrics.includes(metric.name)} onClick={handleMetricCheck} />
                </div>
            ))}
        </div>
    );
};
