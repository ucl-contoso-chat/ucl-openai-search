import { Pivot, PivotItem, Text, DetailsList, DetailsListLayoutMode, SelectionMode } from "@fluentui/react";
import { UploadEvaluationFile } from "./UploadEvaluationFile";
import { GenerateData } from "./GenerateData";

import styles from "./EvaluationDataPanel.module.css";
import { useEffect, useState } from "react";
import { ErrorCircle24Regular } from "@fluentui/react-icons";

interface Props {
    isUploading: boolean;
    setIsUploading: (isUploading: boolean) => void;
    evalFile: File | null;
    setEvalFile: (evalFile: File | null) => void;
    numberOfLines: number;
    setNumberOfLines: (numberOfLines: number) => void;
}

export const EvaluationDataPanel: React.FC<Props> = ({ isUploading, setIsUploading, evalFile, setEvalFile, numberOfLines, setNumberOfLines }: Props) => {
    const [generateFileDownloadUrl, setGenerateFileDownloadUrl] = useState<string | null>(null);
    const [evalDataList, setEvalDataList] = useState<JSON[]>([]);
    const [error, setError] = useState<string>("");
    const [evalDataColumns, setEvalDataColumns] = useState<any[]>([]);

    const readEvalFile = async () => {
        const reader = new FileReader();
        if (!evalFile) {
            return;
        }
        reader.readAsText(evalFile, "UTF-8");
        reader.onload = async e => {
            const content = e.target?.result;
            if (typeof content === "string") {
                const lines = content.split("\n");
                const jsonObjects: JSON[] = [];
                lines.forEach((line, index) => {
                    if (line.trim()) {
                        try {
                            const jsonObject = JSON.parse(line);
                            if (jsonObject["question"] && jsonObject["truth"]) {
                                jsonObjects.push(jsonObject);
                            } else {
                                throw new Error("Invalid JSON object");
                            }
                        } catch (err) {
                            setError(`Error in parsing line ${index + 1}`);
                            return;
                        }
                    }
                });
                setEvalDataColumns([
                    { key: "question", name: "Question", fieldName: "question", minWidth: 100, maxWidth: 300, isResizable: true },
                    { key: "truth", name: "Truth", fieldName: "truth", minWidth: 100, isResizable: true }
                ]);
                setEvalDataList(jsonObjects);
                console.log(jsonObjects);
                setNumberOfLines(jsonObjects.length);
            }
        };
    };

    useEffect(() => {
        if (evalFile) {
            readEvalFile();
        }
    }, [evalFile]);

    return (
        <div>
            <Pivot className={styles.evaluateDataPivotContainer}>
                <PivotItem className={styles.evaluateDataPivotItem} headerText={"Upload"} itemIcon={"Upload"}>
                    <UploadEvaluationFile
                        isUploading={isUploading}
                        setIsUploading={setIsUploading}
                        uploadedFile={evalFile}
                        setUploadedFile={setEvalFile}
                        numberOfLines={numberOfLines}
                        setNumberOfLines={setNumberOfLines}
                    />
                </PivotItem>
                <PivotItem className={styles.evaluateDataPivotItem} headerText={"Generate"} itemIcon={"BrowserTab"}>
                    <GenerateData
                        generatedFile={evalFile}
                        setGeneratedFile={setEvalFile}
                        numberOfLines={numberOfLines}
                        setNumberOfLines={setNumberOfLines}
                        generateFileDownloadUrl={generateFileDownloadUrl}
                        setGenerateFileDownloadUrl={setGenerateFileDownloadUrl}
                        inProgress={isUploading}
                        setInProgress={setIsUploading}
                    />
                </PivotItem>
            </Pivot>

            {error !== "" ? (
                <div className={styles.errorContainer}>
                    <ErrorCircle24Regular aria-hidden="true" aria-label="Error icon" primaryFill="red" />
                    {error}
                </div>
            ) : null}

            <hr />

            <Text className={styles.fileText} block={true} variant="mediumPlus">
                {`The file you use contains ${numberOfLines} lines`}
            </Text>

            {evalDataList.length > 0 && (
                <div>
                    <Text className={styles.fileText} block={true} variant="mediumPlus">
                        {" "}
                        Data Preview ({evalDataList.length > 10 && <i>Only showing the first 10 lines</i>})
                    </Text>

                    <DetailsList
                        className={styles.evalDataList}
                        items={evalDataList.slice(0, Math.min(10, evalDataList.length))}
                        columns={evalDataColumns}
                        selectionMode={SelectionMode.none}
                        layoutMode={DetailsListLayoutMode.justified}
                        compact={true}
                        data-is-scrollable={true}
                    />
                </div>
            )}
        </div>
    );
};
