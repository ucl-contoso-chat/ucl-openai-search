import { CheckmarkCircleSquare24Regular, ErrorCircle24Regular, ArrowDownload24Filled } from "@fluentui/react-icons";
import { Spinner, SpinnerSize } from "@fluentui/react/lib/Spinner";
import { Button } from "@fluentui/react-components";

import styles from "./EvaluateButton.module.css";
import { Label, DefaultButton } from "@fluentui/react";

interface Props {
    className?: string;
    inProgress: boolean;
    onClick: () => void;
    evalResDownloadUrl?: string;
}

export const EvaluateButton = ({ className, inProgress, onClick, evalResDownloadUrl }: Props) => {
    return (
        <div className={`${styles.container} ${className ?? ""}`}>
            {(evalResDownloadUrl && (
                <DefaultButton className={styles.evaluateButton} disabled={inProgress} download="evaluation-result.pdf" href={evalResDownloadUrl}>
                    <ArrowDownload24Filled />
                    {"Download Evaluation Result Report "}
                </DefaultButton>
            )) || (
                <DefaultButton className={styles.evaluateButton} onClick={onClick} disabled={inProgress}>
                    {(inProgress && (
                        <div className={styles.progressContainer}>
                            <Spinner size={SpinnerSize.medium} />
                            <Label> {" Running Evaluation... "}</Label>
                        </div>
                    )) || (
                        <div>
                            <CheckmarkCircleSquare24Regular />
                            {"Run Evaluation "}
                        </div>
                    )}
                </DefaultButton>
            )}
        </div>
    );
};
