import styles from "./EvaluationMetric.module.css";

interface Props {
    metric: { name: string; display_name: string; description: string; [otherProps: string]: unknown };
    checked: boolean;
    onClick: (metricName: string, checked: boolean) => void;
}

export const EvaluationMetric = ({ metric, checked, onClick }: Props) => {
    return (
        <div
            title={metric.name}
            className={(checked ? styles.metricContainerSelected : styles.metricContainer) + " " + styles.hideScrollbar}
            onClick={() => onClick(metric.name, checked)}
        >
            <div className={styles.metricTitle}>{metric.display_name}</div>
            <div className={styles.metricDescription + " " + styles.hideScrollbar}>{metric.description}</div>
        </div>
    );
};
