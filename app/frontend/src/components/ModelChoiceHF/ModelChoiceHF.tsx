import { useEffect, useState } from "react";
import { Stack, IDropdownOption, Dropdown, IDropdownProps, List } from "@fluentui/react";
import { useId } from "@fluentui/react-hooks";

import { HelpCallout } from "../../components/HelpCallout";
import { toolTipText } from "../../i18n/tooltips.js";

interface Props {
    defaultHFModel: string;
    modelsList: string[];
    updateCurrentModel: (hf_model: string) => void;
}

export const ModelChoiceHF = ({ updateCurrentModel, defaultHFModel, modelsList }: Props) => {
    const [hf_model, setHfModel] = useState<String>(defaultHFModel);

    const onHfModelChange = (_ev: React.FormEvent<HTMLDivElement>, option?: IDropdownOption<string> | undefined) => {
        setHfModel(option?.data || "");
        updateCurrentModel(option?.data || "");
    };

    const hfModelId = useId("hfModel");
    const hfModelFieldId = useId("hfModelField");
    const modelsMapping = modelsList.map(model => ({
        key: model,
        text: model
    }));
    console.log(defaultHFModel);
    console.log(modelsList);
    return (
        <Stack tokens={{ childrenGap: 10 }}>
            <Dropdown
                id={hfModelFieldId}
                label="HuggingFace Model"
                selectedKey={hf_model.toString()}
                options={modelsMapping}
                required
                onChange={onHfModelChange}
                aria-labelledby={hfModelId}
                onRenderLabel={(props: IDropdownProps | undefined) => (
                    <HelpCallout labelId={hfModelId} fieldId={hfModelFieldId} helpText={toolTipText.retrievalMode} label={props?.label} />
                )}
            />
        </Stack>
    );
};
