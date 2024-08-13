import { useState } from "react";
import { useLogin, getToken, requireAccessControl } from "../../../authConfig";
import { useId } from "@fluentui/react-hooks";
import styles from "./GenerateData.module.css";

import { DefaultButton, TextField, Text, Spinner, SpinnerSize, Label, Link } from "@fluentui/react";
import { useMsal } from "@azure/msal-react";
import { generateApi } from "../../../api";
import { ErrorCircle24Regular } from "@fluentui/react-icons";

interface Props {
    generatedFile: File | null;
    setGeneratedFile: (generatedFile: File | null) => void;
    numberOfLines: number;
    setNumberOfLines: (numberOfLines: number) => void;
    generateFileDownloadUrl: string | null;
    setGenerateFileDownloadUrl: (generateFileDownloadUrl: string | null) => void;
    inProgress: boolean;
    setInProgress: (inProgress: boolean) => void;
}

export const GenerateData: React.FC<Props> = ({
    generatedFile,
    setGeneratedFile,
    numberOfLines,
    setNumberOfLines,
    generateFileDownloadUrl,
    setGenerateFileDownloadUrl,
    inProgress,
    setInProgress
}: Props) => {
    const [numQuestions, setNumQuestions] = useState<number>(1);
    const [perSource, setPerSource] = useState<number>(5);

    const numQuestionsId = useId("numQuestions");
    const numQuestionsFieldId = useId("numQuestionsField");
    const perSourceId = useId("perSource");
    const perSourceFieldId = useId("perSourceField");
    const [generateError, setGenerateError] = useState<string>("");

    const client = useLogin ? useMsal().instance : undefined;

    const makeGenerateRequest = async () => {
        setInProgress(true);
        const requestData: FormData = new FormData();
        if (numQuestions === 0) {
            setGenerateError("Please enter the number of questions you want to generate");
            setInProgress(false);
            return;
        } else {
            requestData.append("num_questions", numQuestions.toString());
        }
        if (perSource === 0) {
            setGenerateError("Please enter the number of questions per source");
            setInProgress(false);
            return;
        } else {
            requestData.append("per_source", perSource.toString());
        }

        const token = client ? await getToken(client) : undefined;
        try {
            const response: Blob = await generateApi(requestData, token);
            const responseFile = new File([response], "generated_data.jsonl");
            setGeneratedFile(responseFile);
            readGenerateData(responseFile);
            const url = window.URL || window.webkitURL;
            const downloadUrl = url.createObjectURL(response);
            setGenerateFileDownloadUrl(downloadUrl);
        } catch (error) {
            setGenerateError("Error in generating data");
        } finally {
            setInProgress(false);
        }
    };

    const readGenerateData = async (file: File) => {
        if (file.name.split(".").pop() !== "jsonl" && file.name.split(".").pop() !== "jsonl") {
            setGenerateError(`The file must be a JSON or JSONL file.`);
            setInProgress(false);
            setGeneratedFile(null);
            return;
        }
    };

    const onNumQuestionChange = (_ev?: React.SyntheticEvent<HTMLElement, Event>, newValue?: string) => {
        setNumQuestions(parseInt(newValue || "0"));
    };

    const onPerSourceChange = (_ev?: React.SyntheticEvent<HTMLElement, Event>, newValue?: string) => {
        setPerSource(parseInt(newValue || "0"));
    };
    return (
        <div>
            <div>
                <TextField
                    id={numQuestionsFieldId}
                    label="Number of questions to generate"
                    type="number"
                    min={1}
                    step={1}
                    defaultValue={numQuestions.toString()}
                    onChange={onNumQuestionChange}
                    aria-labelledby={numQuestionsId}
                />
                <TextField
                    id={perSourceFieldId}
                    label="Number of questions per source"
                    type="number"
                    min={1}
                    step={1}
                    defaultValue={perSource.toString()}
                    onChange={onPerSourceChange}
                    aria-labelledby={perSourceId}
                />
            </div>
            <div className={styles.generatButtonContainer}>
                <DefaultButton onClick={makeGenerateRequest} disabled={inProgress}>
                    {inProgress ? (
                        <div className={styles.progressContainer}>
                            <Spinner size={SpinnerSize.medium} />
                            <Label> {" Generating Data... "}</Label>
                        </div>
                    ) : (
                        "Generate"
                    )}
                </DefaultButton>
            </div>

            {generateFileDownloadUrl && (
                <Link href={generateFileDownloadUrl} download={generatedFile !== null ? generatedFile.name : "generate_result.jsonl"}>
                    {"Download the generated data"}
                </Link>
            )}
        </div>
    );
};
