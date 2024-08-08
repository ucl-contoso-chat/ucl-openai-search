export const metrics = [
    {
        name: "gpt_groundedness",
        display_name: "Groundedness",
        description:
            "Groundness assesses the correspondence between claims in an AI-generated answer and the source context, making sure that these claims are substantiated by the context."
    },
    {
        name: "gpt_relevance",
        display_name: "Relevance",
        description: "Relevance assesses the ability of answers to capture the key points of the context."
    },
    {
        name: "gpt_coherence",
        display_name: "Coherence",
        description:
            "Coherence measures how well the language model can produce output that flows smoothly, reads naturally, and resembles human-like language."
    },
    {
        name: "gpt_similarity",
        display_name: "Simliarity",
        description: "Simliarity measures the similarity between a source data (ground truth) sentence and the generated response by an AI model."
    },
    {
        name: "gpt_fluency",
        display_name: "Fluency",
        description: "Fluency measures the grammatical proficiency of a generative AI's predicted answer."
    },
    {
        name: "f1_score",
        display_name: "F1 Score",
        description: "F1 score measures the ratio of the number of shared words between the model generation and the ground truth answers."
    },
    {
        name: "answer_length",
        display_name: "Answer Length",
        description: "The length of the generated answer, in characters."
    },
    {
        name: "latency",
        display_name: "Latency",
        description: "The time it takes for the chat app to generate an answer, in seconds."
    }
];
