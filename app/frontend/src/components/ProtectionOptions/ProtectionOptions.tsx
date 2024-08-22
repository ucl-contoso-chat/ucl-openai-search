import { Checkbox } from "@fluentui/react";

import { ProtectionConfig } from "../../api";

interface Props {
    protectionConfig: Record<string, ProtectionConfig>;
    updateProtectionConfig: (name: string, checked: boolean) => void;
    checkboxClassName?: string;
}

export const ProtectionOptions = ({ updateProtectionConfig, protectionConfig, checkboxClassName }: Props) => {
    const handleCheckboxChange = (ev?: React.FormEvent<HTMLInputElement | HTMLElement>, checked?: boolean) => {
        const target = ev?.target as HTMLInputElement;
        const name = target.name;
        updateProtectionConfig(name, checked ?? false);
    };

    const formatOptionName = (option: string): string => {
        const first_part = option.split("_")[0];

        return `${first_part.charAt(0).toUpperCase()}${first_part.slice(1)} protection`;
    };

    return (
        <>
            {Object.keys(protectionConfig).map(key => (
                <Checkbox
                    key={key}
                    name={key}
                    className={checkboxClassName}
                    label={formatOptionName(key)}
                    checked={protectionConfig[key].enabled} // Defaults to false if the key doesn't exist
                    onChange={handleCheckboxChange}
                    aria-labelledby={key}
                />
            ))}
        </>
    );
};
