import React, { ChangeEvent, useEffect, useState } from "react";
import { Label, Text, Pivot, PivotItem, TextField, DefaultButton } from "@fluentui/react";

import styles from "./UploadEvaluationFile.module.css";

interface Props {
    className?: string;
    isUploading: boolean;
    setIsUploading: (isUploading: boolean) => void;
    uploadedFile: File | null;
    setUploadedFile: (file: File | null) => void;
    numberOfLines: number;
    setNumberOfLines: (numberOfLines: number) => void;
}

export const UploadEvaluationFile: React.FC<Props> = ({
    className,
    isUploading,
    setIsUploading,
    uploadedFile,
    setUploadedFile,
    numberOfLines,
    setNumberOfLines
}: Props) => {
    const [fileContent, setFileContent] = useState<JSON[]>([]);
    const [uploadedFileError, setUploadedFileError] = useState<string>();

    // Handler for the form submission (file upload)
    const handleUploadFile = async (e: ChangeEvent<HTMLInputElement>) => {
        setIsUploading(true);
        // Reset the uploaded file and file content
        setUploadedFile(null);
        setFileContent([]);

        e.preventDefault();
        const reader = new FileReader();
        if (!e.target.files || e.target.files.length === 0) {
            setUploadedFileError(`No files selected or the file does not contain any data.`);
            return;
        }
        const file: File = e.target.files[0];
        console.log(file);
        if (file.name.split(".").pop() !== "jsonl" && file.name.split(".").pop() !== "jsonl") {
            setUploadedFileError(`The file must be a JSON or JSONL file.`);
            setIsUploading(false);
            return;
        }
        reader.readAsText(file, "UTF-8");
        reader.onload = async e => {
            const content = e.target?.result;
            if (typeof content === "string") {
                const lines = content.split("\n");
                const jsonObjects: JSON[] = [];
                lines.forEach((line, index) => {
                    if (line.trim()) {
                        try {
                            const jsonObject = JSON.parse(line);
                            jsonObjects.push(jsonObject);
                        } catch (err) {
                            setUploadedFileError(`Error parsing line ${index + 1}`);
                            setIsUploading(false);
                        }
                    }
                });
                setUploadedFileError(undefined);
                setFileContent(jsonObjects);
                setNumberOfLines(jsonObjects.length);
            }
        };
        setUploadedFile(file);
        setIsUploading(false);
    };

    return (
        <div className={`${styles.container} ${className ?? ""}`}>
            <div>
                <form>
                    <div>
                        <Label>Upload file:</Label>
                        <input accept=".jsonl" className={styles.chooseFiles} type="file" onChange={handleUploadFile} />
                    </div>
                </form>

                {/* Show a loading message while files are being uploaded */}
                {isUploading && <Text block={true}>{"Uploading files..."}</Text>}
                {!isUploading && uploadedFile === null && <Text block={true}>No files uploaded yet</Text>}
            </div>
        </div>
    );
};
