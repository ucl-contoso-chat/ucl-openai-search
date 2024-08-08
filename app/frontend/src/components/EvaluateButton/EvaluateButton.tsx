import { CheckmarkCircleSquare24Regular, ErrorCircle24Regular } from "@fluentui/react-icons";
import { Spinner, SpinnerSize } from "@fluentui/react/lib/Spinner";
import { Button } from "@fluentui/react-components";

import styles from "./EvaluateButton.module.css";
import { Label, DefaultButton } from "@fluentui/react";

interface Props {
    className?: string;
    inProgress: boolean;
    onClick: () => void;
}

export const EvaluateButton = ({ className, inProgress, onClick }: Props) => {
    return (
        <div className={`${styles.container} ${className ?? ""}`}>
            {inProgress && (
                <div className={styles.progressContainer}>
                    <Spinner size={SpinnerSize.medium} />
                    <Label> {" Running Evaluation... "}</Label>
                </div>
            )}
            <DefaultButton className={styles.evaluateButton} onClick={onClick} disabled={inProgress}>
                <CheckmarkCircleSquare24Regular />
                {"Run Evaluation "}
            </DefaultButton>
        </div>
    );
};
