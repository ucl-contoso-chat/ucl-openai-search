import { useContext, useEffect, useState } from "react";

import styles from "./Evaluation.module.css";
import { useId } from "@fluentui/react-hooks";
import { Accordion, AccordionHeader, AccordionItem, AccordionPanel, AccordionToggleEventHandler, Card, CardHeader, Text } from "@fluentui/react-components";

import { Checkbox, ICheckboxProps, ITextFieldProps, Link, Pivot, PivotItem, TextField } from "@fluentui/react";
import { ErrorCircle24Regular, NumberCircle132Filled, NumberCircle232Filled, NumberCircle332Filled, NumberCircle432Filled } from "@fluentui/react-icons";
import { configApi, RetrievalMode, VectorFieldOptions, GPT4VInput, SimpleAPIResponse, evaluateApi, generateApi, getSupportedModels } from "../../api";
import { useLogin, getToken, requireAccessControl } from "../../authConfig";
import { HelpCallout } from "../../components/HelpCallout";
import { toolTipText } from "../../i18n/tooltips.js";
import { gpt_metrics, stats_metrics } from "../../i18n/metrics";
import { GPT4VSettings } from "../../components/GPT4VSettings";
import { VectorSettings } from "../../components/VectorSettings";
import { useMsal } from "@azure/msal-react";
import { LoginContext } from "../../loginContext";
import { TokenClaimsDisplay } from "../../components/TokenClaimsDisplay";
import { EvaluateButton } from "../../components/EvaluateButton";
import { EvaluationMetricList } from "../../components/EvaluationMetric";
import { EvaluationDataPanel } from "../../components/EvaluationDataPanel";
import { ModelSelectionPanel } from "../../components/ModelSelectionPanel/ModelSelectionPanel";

export function Component(): JSX.Element {
    const [openItems, setOpenItems] = useState(["1"]);
    const [evalData, setEvalData] = useState<File | null>(null);
    const [numQuestions, setNumQuestions] = useState<number>(0);
    const [numQuestionsToEval, setNumQuestionsToEval] = useState<number>(2);
    const [isUploading, setIsUploading] = useState<boolean>(false);
    const [selectedGPTMetrics, setSelectedGPTMetrics] = useState<{}[]>(gpt_metrics.map(metric => metric.name));
    const [selectedStatsMetrics, setSelectedStatsMetrics] = useState<{}[]>(stats_metrics.map(metric => metric.name));
    const [availableModels, setAvailableModels] = useState<string[]>([]);
    const [selectedModels, setSelectedModels] = useState<string[]>([]);
    const [evalResiltDownloadUrl, setEvalResultDownloadUrl] = useState<string>("");

    const [temperature, setTemperature] = useState<number>(0.3);
    const [minimumRerankerScore, setMinimumRerankerScore] = useState<number>(0);
    const [minimumSearchScore, setMinimumSearchScore] = useState<number>(0);
    const [retrieveCount, setRetrieveCount] = useState<number>(3);
    const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>(RetrievalMode.Hybrid);
    const [useSemanticRanker, setUseSemanticRanker] = useState<boolean>(true);
    const [shouldStream, setShouldStream] = useState<boolean>(true);
    const [useSemanticCaptions, setUseSemanticCaptions] = useState<boolean>(false);
    const [useSuggestFollowupQuestions, setUseSuggestFollowupQuestions] = useState<boolean>(false);
    const [vectorFieldList, setVectorFieldList] = useState<VectorFieldOptions[]>([VectorFieldOptions.Embedding]);
    const [useOidSecurityFilter, setUseOidSecurityFilter] = useState<boolean>(false);
    const [useGroupsSecurityFilter, setUseGroupsSecurityFilter] = useState<boolean>(false);
    const [gpt4vInput, setGPT4VInput] = useState<GPT4VInput>(GPT4VInput.TextAndImages);
    const [useGPT4V, setUseGPT4V] = useState<boolean>(false);
    const [runRedTeaming, setRunRedTeaming] = useState<boolean>(true);

    const [inProgress, setInProgress] = useState<boolean>(false);
    const [error, setError] = useState<unknown>();

    const onNumQuestionsToEvalChange = (_ev?: React.SyntheticEvent<HTMLElement, Event>, newValue?: string) => {
        setNumQuestionsToEval(parseInt(newValue || "2"));
    };

    const onTemperatureChange = (_ev?: React.SyntheticEvent<HTMLElement, Event>, newValue?: string) => {
        setTemperature(parseFloat(newValue || "0"));
    };

    const onMinimumSearchScoreChange = (_ev?: React.SyntheticEvent<HTMLElement, Event>, newValue?: string) => {
        setMinimumSearchScore(parseFloat(newValue || "0"));
    };

    const onMinimumRerankerScoreChange = (_ev?: React.SyntheticEvent<HTMLElement, Event>, newValue?: string) => {
        setMinimumRerankerScore(parseFloat(newValue || "0"));
    };

    const onRetrieveCountChange = (_ev?: React.SyntheticEvent<HTMLElement, Event>, newValue?: string) => {
        setRetrieveCount(parseInt(newValue || "3"));
    };

    const onUseSemanticRankerChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setUseSemanticRanker(!!checked);
    };

    const onUseSemanticCaptionsChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setUseSemanticCaptions(!!checked);
    };

    const onShouldStreamChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setShouldStream(!!checked);
    };

    const onUseSuggestFollowupQuestionsChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setUseSuggestFollowupQuestions(!!checked);
    };

    const onUseOidSecurityFilterChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setUseOidSecurityFilter(!!checked);
    };

    const onUseGroupsSecurityFilterChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setUseGroupsSecurityFilter(!!checked);
    };

    const onRunRedTeamingChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setRunRedTeaming(!!checked);
    };

    // IDs for form labels and their associated callouts
    const numQuestionsId = useId("numQuestions");
    const numQuestionsFieldId = useId("numQuestionsField");
    const temperatureId = useId("temperature");
    const temperatureFieldId = useId("temperatureField");
    const searchScoreId = useId("searchScore");
    const searchScoreFieldId = useId("searchScoreField");
    const rerankerScoreId = useId("rerankerScore");
    const rerankerScoreFieldId = useId("rerankerScoreField");
    const retrieveCountId = useId("retrieveCount");
    const retrieveCountFieldId = useId("retrieveCountField");
    const semanticRankerId = useId("semanticRanker");
    const semanticRankerFieldId = useId("semanticRankerField");
    const semanticCaptionsId = useId("semanticCaptions");
    const semanticCaptionsFieldId = useId("semanticCaptionsField");
    const suggestFollowupQuestionsId = useId("suggestFollowupQuestions");
    const suggestFollowupQuestionsFieldId = useId("suggestFollowupQuestionsField");
    const useOidSecurityFilterId = useId("useOidSecurityFilter");
    const useOidSecurityFilterFieldId = useId("useOidSecurityFilterField");
    const useGroupsSecurityFilterId = useId("useGroupsSecurityFilter");
    const useGroupsSecurityFilterFieldId = useId("useGroupsSecurityFilterField");
    const shouldStreamId = useId("shouldStream");
    const shouldStreamFieldId = useId("shouldStreamField");
    const runRedTeamingId = useId("runRedTeaming");

    const [showGPT4VOptions, setShowGPT4VOptions] = useState<boolean>(false);
    const [showSemanticRankerOption, setShowSemanticRankerOption] = useState<boolean>(false);
    const [showVectorOption, setShowVectorOption] = useState<boolean>(false);

    useEffect(() => {
        getConfig();
        getAvailableModels();
    }, []);

    const getConfig = async () => {
        configApi().then(config => {
            setShowGPT4VOptions(config.showGPT4VOptions);
            setUseSemanticRanker(config.showSemanticRankerOption);
            setShowSemanticRankerOption(config.showSemanticRankerOption);
            setShowVectorOption(config.showVectorOption);

            if (!config.showVectorOption) {
                setRetrievalMode(RetrievalMode.Text);
            }
        });
    };

    const client = useLogin ? useMsal().instance : undefined;
    const { loggedIn } = useContext(LoginContext);

    const getAvailableModels = async () => {
        const models = await getSupportedModels();
        setAvailableModels(models);
        setSelectedModels([models[0]]);
    };

    const makeEvaluationRequest = async () => {
        setInProgress(true);
        const requestData: FormData = new FormData();
        if (evalData === null) {
            setError("Please upload a file to evaluate");
            setInProgress(false);
            return;
        } else {
            requestData.append("input_data", evalData);
        }
        if (selectedGPTMetrics.length === 0) {
            setInProgress(false);
            setError("Please select at least one RAG Evaluation metric to evaluate");
            return;
        }
        if (selectedStatsMetrics.length === 0) {
            setInProgress(false);
            setError("Please select at least one Statistical metric to evaluate");
            return;
        }
        if (numQuestionsToEval === 0) {
            setInProgress(false);
            setError("Please enter the number of questions you want to evaluate");
            return;
        } else {
            setError(null);
            requestData.append("num_questions", numQuestionsToEval.toString());
        }
        if (selectedModels.length === 0) {
            setInProgress(false);
            setError("Please select at least one model to evaluate");
            return;
        }

        setEvalResultDownloadUrl("");

        const selectedMetrics = selectedGPTMetrics.concat(selectedStatsMetrics);

        const config = {
            requested_metrics: selectedMetrics,
            compared_models: selectedModels,
            run_red_teaming: runRedTeaming,
            target_parameters: {
                overrides: {
                    top: retrieveCount,
                    temperature: temperature,
                    minimum_reranker_score: minimumRerankerScore,
                    minimum_search_score: minimumSearchScore,
                    retrieval_mode: retrievalMode,
                    semantic_ranker: useSemanticRanker,
                    semantic_captions: useSemanticCaptions,
                    suggest_followup_questions: useSuggestFollowupQuestions,
                    use_oid_security_filter: useOidSecurityFilter,
                    use_groups_security_filter: useGroupsSecurityFilter,
                    vector_fields: vectorFieldList,
                    use_gpt4v: useGPT4V,
                    gpt4v_input: gpt4vInput
                }
            }
        };
        requestData.append("config", JSON.stringify(config));

        const token = client ? await getToken(client) : undefined;
        try {
            console.log("start");
            const response: Blob = await evaluateApi(requestData, token);
            const url = window.URL || window.webkitURL;
            const downloadUrl = url.createObjectURL(response);
            setEvalResultDownloadUrl(downloadUrl);
        } catch (e) {
            setError(e);
        } finally {
            setInProgress(false);
        }
    };

    const handleToggle: AccordionToggleEventHandler<string> = (event, data) => {
        setOpenItems(data.openItems);
    };

    return (
        <div className={styles.evaluationContainer}>
            <div className={styles.evaluationTopSection}>
                <h1 className={styles.evaluationTitle}>Model Evaluator</h1>
                <h3 className={styles.evaluationInstruction}>Evaluate the application using deployed model</h3>
                <Accordion collapsible multiple openItems={openItems} onToggle={handleToggle} className={styles.evaluationCollapseList}>
                    <AccordionItem value="1" className={styles.evaluationCollapseItem}>
                        <AccordionHeader className={styles.evaluationCollapseTitle} icon={<NumberCircle132Filled primaryFill="rgba(115, 118, 225, 1)" />}>
                            <div className={styles.evaluationAccordionHeader}>{"Choose the model you want to evaluate"}</div>
                        </AccordionHeader>
                        <AccordionPanel>
                            <ModelSelectionPanel models={availableModels} selectedModels={selectedModels} setSelectedModels={setSelectedModels} />
                        </AccordionPanel>
                    </AccordionItem>
                    <AccordionItem value="2" className={styles.evaluationCollapseItem}>
                        <AccordionHeader className={styles.evaluationCollapseTitle} icon={<NumberCircle232Filled primaryFill="rgba(115, 118, 225, 1)" />}>
                            <div className={styles.evaluationAccordionHeader}>{"Choose Your Test Data"}</div>
                        </AccordionHeader>
                        <AccordionPanel>
                            <EvaluationDataPanel
                                isUploading={isUploading}
                                setIsUploading={setIsUploading}
                                evalFile={evalData}
                                setEvalFile={setEvalData}
                                numberOfLines={numQuestions}
                                setNumberOfLines={setNumQuestions}
                            />
                            <div>
                                {evalData !== null && (
                                    <TextField
                                        id={numQuestionsFieldId}
                                        className={styles.evaluateSettingsSeparator}
                                        label="Number of questions you want to evaluate"
                                        type="number"
                                        min={2}
                                        max={numQuestions}
                                        defaultValue={numQuestionsToEval.toString()}
                                        onChange={onNumQuestionsToEvalChange}
                                        aria-labelledby={numQuestionsId}
                                    />
                                )}
                            </div>
                        </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem value="3" className={styles.evaluationCollapseItem}>
                        <AccordionHeader className={styles.evaluationCollapseTitle} icon={<NumberCircle332Filled primaryFill="rgba(115, 118, 225, 1)" />}>
                            <div className={styles.evaluationAccordionHeader}>{"Select Evaluation Metrics"}</div>
                        </AccordionHeader>
                        <AccordionPanel>
                            <div>
                                <h3>RAG Evaluation Metrics</h3>
                                <hr />
                                <br />
                                <div className={styles.evaluationMetricContainer}>
                                    <EvaluationMetricList
                                        metrics={gpt_metrics}
                                        selectedMetrics={selectedGPTMetrics}
                                        setSelectedMetrics={setSelectedGPTMetrics}
                                    />
                                </div>
                                <h3>Statistical Metrics</h3>
                                <hr />
                                <br />
                                <div className={styles.evaluationMetricContainer}>
                                    <EvaluationMetricList
                                        metrics={stats_metrics}
                                        selectedMetrics={selectedStatsMetrics}
                                        setSelectedMetrics={setSelectedStatsMetrics}
                                    />
                                </div>
                            </div>
                        </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem value="4" className={styles.evaluationCollapseItem}>
                        <AccordionHeader className={styles.evaluationCollapseTitle} icon={<NumberCircle432Filled primaryFill="rgba(115, 118, 225, 1)" />}>
                            <div className={styles.evaluationAccordionHeader}>{"Application Settings"}</div>
                        </AccordionHeader>
                        <AccordionPanel>
                            <div className={styles.configPanel}>
                                <Checkbox
                                    id={runRedTeamingId}
                                    className={styles.evaluateSettingsSeparator}
                                    checked={runRedTeaming}
                                    label="Run red teaming"
                                    onChange={onRunRedTeamingChange}
                                    aria-labelledby={runRedTeamingId}
                                    onRenderLabel={(props: ICheckboxProps | undefined) => (
                                        <HelpCallout
                                            labelId={runRedTeamingId}
                                            fieldId={runRedTeamingId}
                                            helpText={toolTipText.runRedTeaming}
                                            label={props?.label}
                                        />
                                    )}
                                />
                                <TextField
                                    id={temperatureFieldId}
                                    className={styles.evaluateSettingsSeparator}
                                    label="Temperature"
                                    type="number"
                                    min={0}
                                    max={1}
                                    step={0.1}
                                    defaultValue={temperature.toString()}
                                    onChange={onTemperatureChange}
                                    aria-labelledby={temperatureId}
                                    onRenderLabel={(props: ITextFieldProps | undefined) => (
                                        <HelpCallout
                                            labelId={temperatureId}
                                            fieldId={temperatureFieldId}
                                            helpText={toolTipText.temperature}
                                            label={props?.label}
                                        />
                                    )}
                                />

                                <TextField
                                    id={searchScoreFieldId}
                                    className={styles.evaluateSettingsSeparator}
                                    label="Minimum search score"
                                    type="number"
                                    min={0}
                                    step={0.01}
                                    defaultValue={minimumSearchScore.toString()}
                                    onChange={onMinimumSearchScoreChange}
                                    aria-labelledby={searchScoreId}
                                    onRenderLabel={(props: ITextFieldProps | undefined) => (
                                        <HelpCallout
                                            labelId={searchScoreId}
                                            fieldId={searchScoreFieldId}
                                            helpText={toolTipText.searchScore}
                                            label={props?.label}
                                        />
                                    )}
                                />

                                {showSemanticRankerOption && (
                                    <TextField
                                        id={rerankerScoreFieldId}
                                        className={styles.evaluateSettingsSeparator}
                                        label="Minimum reranker score"
                                        type="number"
                                        min={1}
                                        max={4}
                                        step={0.1}
                                        defaultValue={minimumRerankerScore.toString()}
                                        onChange={onMinimumRerankerScoreChange}
                                        aria-labelledby={rerankerScoreId}
                                        onRenderLabel={(props: ITextFieldProps | undefined) => (
                                            <HelpCallout
                                                labelId={rerankerScoreId}
                                                fieldId={rerankerScoreFieldId}
                                                helpText={toolTipText.rerankerScore}
                                                label={props?.label}
                                            />
                                        )}
                                    />
                                )}

                                <TextField
                                    id={retrieveCountFieldId}
                                    className={styles.evaluateSettingsSeparator}
                                    label="Retrieve this many search results:"
                                    type="number"
                                    min={1}
                                    max={50}
                                    defaultValue={retrieveCount.toString()}
                                    onChange={onRetrieveCountChange}
                                    aria-labelledby={retrieveCountId}
                                    onRenderLabel={(props: ITextFieldProps | undefined) => (
                                        <HelpCallout
                                            labelId={retrieveCountId}
                                            fieldId={retrieveCountFieldId}
                                            helpText={toolTipText.retrieveNumber}
                                            label={props?.label}
                                        />
                                    )}
                                />

                                {showSemanticRankerOption && (
                                    <>
                                        <Checkbox
                                            id={semanticRankerFieldId}
                                            className={styles.evaluateSettingsSeparator}
                                            checked={useSemanticRanker}
                                            label="Use semantic ranker for retrieval"
                                            onChange={onUseSemanticRankerChange}
                                            aria-labelledby={semanticRankerId}
                                            onRenderLabel={(props: ICheckboxProps | undefined) => (
                                                <HelpCallout
                                                    labelId={semanticRankerId}
                                                    fieldId={semanticRankerFieldId}
                                                    helpText={toolTipText.useSemanticReranker}
                                                    label={props?.label}
                                                />
                                            )}
                                        />

                                        <Checkbox
                                            id={semanticCaptionsFieldId}
                                            className={styles.evaluateSettingsSeparator}
                                            checked={useSemanticCaptions}
                                            label="Use semantic captions"
                                            onChange={onUseSemanticCaptionsChange}
                                            disabled={!useSemanticRanker}
                                            aria-labelledby={semanticCaptionsId}
                                            onRenderLabel={(props: ICheckboxProps | undefined) => (
                                                <HelpCallout
                                                    labelId={semanticCaptionsId}
                                                    fieldId={semanticCaptionsFieldId}
                                                    helpText={toolTipText.useSemanticCaptions}
                                                    label={props?.label}
                                                />
                                            )}
                                        />
                                    </>
                                )}

                                <Checkbox
                                    id={suggestFollowupQuestionsFieldId}
                                    className={styles.evaluateSettingsSeparator}
                                    checked={useSuggestFollowupQuestions}
                                    label="Suggest follow-up questions"
                                    onChange={onUseSuggestFollowupQuestionsChange}
                                    aria-labelledby={suggestFollowupQuestionsId}
                                    onRenderLabel={(props: ICheckboxProps | undefined) => (
                                        <HelpCallout
                                            labelId={suggestFollowupQuestionsId}
                                            fieldId={suggestFollowupQuestionsFieldId}
                                            helpText={toolTipText.suggestFollowupQuestions}
                                            label={props?.label}
                                        />
                                    )}
                                />

                                {showGPT4VOptions && (
                                    <GPT4VSettings
                                        gpt4vInputs={gpt4vInput}
                                        isUseGPT4V={useGPT4V}
                                        updateUseGPT4V={useGPT4V => {
                                            setUseGPT4V(useGPT4V);
                                        }}
                                        updateGPT4VInputs={inputs => setGPT4VInput(inputs)}
                                    />
                                )}

                                {showVectorOption && (
                                    <VectorSettings
                                        defaultRetrievalMode={retrievalMode}
                                        showImageOptions={useGPT4V && showGPT4VOptions}
                                        updateVectorFields={(options: VectorFieldOptions[]) => setVectorFieldList(options)}
                                        updateRetrievalMode={(retrievalMode: RetrievalMode) => setRetrievalMode(retrievalMode)}
                                    />
                                )}

                                {useLogin && (
                                    <>
                                        <Checkbox
                                            id={useOidSecurityFilterFieldId}
                                            className={styles.evaluateSettingsSeparator}
                                            checked={useOidSecurityFilter || requireAccessControl}
                                            label="Use oid security filter"
                                            disabled={!loggedIn || requireAccessControl}
                                            onChange={onUseOidSecurityFilterChange}
                                            aria-labelledby={useOidSecurityFilterId}
                                            onRenderLabel={(props: ICheckboxProps | undefined) => (
                                                <HelpCallout
                                                    labelId={useOidSecurityFilterId}
                                                    fieldId={useOidSecurityFilterFieldId}
                                                    helpText={toolTipText.useOidSecurityFilter}
                                                    label={props?.label}
                                                />
                                            )}
                                        />
                                        <Checkbox
                                            id={useGroupsSecurityFilterFieldId}
                                            className={styles.evaluateSettingsSeparator}
                                            checked={useGroupsSecurityFilter || requireAccessControl}
                                            label="Use groups security filter"
                                            disabled={!loggedIn || requireAccessControl}
                                            onChange={onUseGroupsSecurityFilterChange}
                                            aria-labelledby={useGroupsSecurityFilterId}
                                            onRenderLabel={(props: ICheckboxProps | undefined) => (
                                                <HelpCallout
                                                    labelId={useGroupsSecurityFilterId}
                                                    fieldId={useGroupsSecurityFilterFieldId}
                                                    helpText={toolTipText.useGroupsSecurityFilter}
                                                    label={props?.label}
                                                />
                                            )}
                                        />
                                    </>
                                )}

                                <Checkbox
                                    id={shouldStreamFieldId}
                                    className={styles.evaluateSettingsSeparator}
                                    checked={shouldStream}
                                    label="Stream chat completion responses"
                                    onChange={onShouldStreamChange}
                                    aria-labelledby={shouldStreamId}
                                    onRenderLabel={(props: ICheckboxProps | undefined) => (
                                        <HelpCallout
                                            labelId={shouldStreamId}
                                            fieldId={shouldStreamFieldId}
                                            helpText={toolTipText.streamChat}
                                            label={props?.label}
                                        />
                                    )}
                                />

                                {useLogin && <TokenClaimsDisplay />}
                            </div>
                        </AccordionPanel>
                    </AccordionItem>
                </Accordion>

                <div className={styles.evaluationFooter}>
                    {error ? (
                        <div className={styles.errorContainer}>
                            <ErrorCircle24Regular aria-hidden="true" aria-label="Error icon" primaryFill="red" className={styles.icon} />
                            {error.toString()}
                        </div>
                    ) : null}

                    <EvaluateButton inProgress={inProgress} onClick={makeEvaluationRequest} evalResDownloadUrl={evalResiltDownloadUrl}></EvaluateButton>
                    {evalResiltDownloadUrl && (
                        <Link className={styles.rerunLink} onClick={makeEvaluationRequest}>
                            {"Run Evaluation Again"}
                        </Link>
                    )}
                </div>
            </div>
        </div>
    );
}

Component.displayName = "Evaluation";
