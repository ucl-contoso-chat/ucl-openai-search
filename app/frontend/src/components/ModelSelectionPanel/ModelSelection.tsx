import styles from "./ModelSelectionPanel.module.css";

interface Props {
    model: string;
    checked: boolean;
    onClick: (model: string, checked: boolean) => void;
}

export const ModelSelection = ({ model, checked, onClick }: Props) => {
    return (
        <div title={model} className={checked ? styles.modelContainerSelected : styles.modelContainer} onClick={() => onClick(model, checked)}>
            <div className={styles.modelTitle}>{model}</div>
        </div>
    );
};
