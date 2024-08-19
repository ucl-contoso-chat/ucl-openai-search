import { ModelSelection } from "./ModelSelection";
import styles from "./ModelSelectionPanel.module.css";

interface Props {
    models: string[];
    selectedModels: string[];
    setSelectedModels: (selectedModels: string[]) => void;
}

export const ModelSelectionPanel = ({ models, selectedModels, setSelectedModels }: Props) => {
    const handleModelCheck = (model?: string, checked?: boolean) => {
        if (typeof model === "string") {
            var selectedModelsArray = [...selectedModels];
            if (!!!checked) {
                if (!selectedModelsArray.includes(model)) {
                    selectedModelsArray.push(model);
                }
            } else {
                if (selectedModelsArray.includes(model)) {
                    selectedModelsArray.splice(selectedModels.indexOf(model), 1);
                }
            }
            setSelectedModels(selectedModelsArray);
        }
    };

    console.log(selectedModels);

    return (
        <div>
            {selectedModels.length > 0 ? (
                <div className={styles.hintText}>
                    {(selectedModels.length == 1 && <div>Selected 1 model for evaluation.</div>) || (
                        <div>Selected {selectedModels.length} models for evaluation and comparison.</div>
                    )}
                </div>
            ) : (
                <div className={styles.hintText}>{"Please select at least 1 model for evaluation."}</div>
            )}
            <div className={styles.modelSelectionPanelContainer}>
                {models.map((model, i) => (
                    <div key={i}>
                        <ModelSelection model={model} checked={selectedModels.includes(model)} onClick={handleModelCheck} />
                    </div>
                ))}
            </div>
        </div>
    );
};
