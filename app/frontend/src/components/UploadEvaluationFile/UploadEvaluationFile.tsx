import React, { ChangeEvent, useEffect, useState } from "react";
import { Label, Text } from "@fluentui/react";

import { useLogin, getToken } from "../../authConfig";
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
        setIsUploading(true); // Start the loading state
        e.preventDefault();
        const reader = new FileReader();
        if (!e.target.files || e.target.files.length === 0) {
            setUploadedFileError(`No files selected or the file does not contain any data.`);
            return;
        }
        const file: File = e.target.files[0];
        reader.readAsText(e.target.files[0], "UTF-8");
        reader.onload = async e => {
            console.log("File loaded");
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
                        }
                    }
                });
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
                {isUploading && <Text>{"Uploading files..."}</Text>}
                {!isUploading && uploadedFile === null && <Text>No files uploaded yet</Text>}
                {!isUploading && uploadedFileError && <Text>{uploadedFileError}</Text>}
                {uploadedFile !== null && numberOfLines > 0 && <Text>{`This file contains ${numberOfLines} lines of data.`}</Text>}
            </div>
        </div>
    );
};
