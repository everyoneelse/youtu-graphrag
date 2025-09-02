from models.constructor import kt_gen as constructor
from models.retriever import agentic_decomposer as decomposer, enhanced_kt_retriever as retriever
from utils.eval import Eval
from config import get_config, ConfigManager
import json
import json_repair
import time
import logging
import argparse
from typing import List

"""
- noagent: Basic retrieval and answer generation
- agent: Question decomposition with parallel sub-question processing and Iterative Retrieval Chain of Thought with step-by-step reasoning
"""

def rerank_chunks_by_keywords(chunks: List[str], question: str, top_k: int) -> List[str]:
    """
    Rerank chunks by keyword matching with the question
    
    Args:
        chunks: List of chunk contents
        question: Original question
        top_k: Number of top chunks to return
        
    Returns:
        Reranked list of chunks
    """
    if len(chunks) <= top_k:
        return chunks
    
    question_keywords = set(question.lower().split())
    scored_chunks = []
    
    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(1 for keyword in question_keywords if keyword in chunk_lower)
        scored_chunks.append((chunk, score))
    
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    
    return [chunk for chunk, score in scored_chunks[:top_k]]


def deduplicate_triples(triples: List[str]) -> List[str]:

    return list(set(triples))


def merge_chunk_contents(chunk_ids, chunk_contents_dict):

    return [chunk_contents_dict.get(chunk_id, f"[Missing content for chunk {chunk_id}]") for chunk_id in chunk_ids]


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Youtu-GraphRAG Framework")
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/base_config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--datasets", 
        nargs="+", 
        default=["demo"],
        help="List of datasets to process"
    )

    parser.add_argument(
        "--override",
        type=str,
        help="JSON string with configuration overrides"
    )
    return parser.parse_args()


def setup_environment(config: ConfigManager):
    """Set up the environment based on configuration."""
    config.setup_logging()
    config.create_output_directories()
    
    logging.info("Youtu-GraphRAG initialized")
    logging.info(f"Mode: {config.triggers.mode}")
    logging.info(f"Constructor enabled: {config.triggers.constructor_trigger}")
    logging.info(f"Retriever enabled: {config.triggers.retrieve_trigger}")


if __name__ == "__main__":
    args = parse_arguments()

    config_path = args.config
    config = get_config(config_path)
    
    if args.override:
        try:
            overrides = json.loads(args.override)
            config.override_config(overrides)
            logging.info("Applied configuration overrides")
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in override parameter: {e}")
            exit(1)
    
    setup_environment(config)
    
    datasets = args.datasets
    
    # ########### Construction ###########
    if config.triggers.constructor_trigger:
        logging.info("Starting knowledge graph construction...")
        
        for dataset in datasets:
            try:
                dataset_config = config.get_dataset_config(dataset)
                logging.info(f"Building knowledge graph for dataset: {dataset}")
                
                builder = constructor.KTBuilder(
                    dataset, 
                    config.api.llm_api_key, 
                    dataset_config.schema_path, 
                    mode=config.construction.mode,
                    config=config
                )

                knowledge_graph = builder.build_knowledge_graph(dataset_config.corpus_path)
                logging.info(f"Successfully built knowledge graph for {dataset}")
                
            except Exception as e:
                logging.error(f"Failed to build knowledge graph for {dataset}: {e}")
                continue

    # ########### Retriever ###########
    if config.triggers.retrieve_trigger:
        logging.info("Starting knowledge retrieval and QA...")
        
        for dataset in datasets:
            try:
                dataset_config = config.get_dataset_config(dataset)
                
                log_file = f"{config.output.logs_dir}/{dataset}_{config.triggers.mode}_recall_{config.retrieval.recall_paths}_{config.retrieval.top_k_filter}.log"
                dataset_logger = logging.getLogger(f"{dataset}_logger")
                dataset_handler = logging.FileHandler(log_file)
                dataset_handler.setFormatter(logging.Formatter(config.logging_config.format))
                dataset_logger.addHandler(dataset_handler)
                dataset_logger.setLevel(getattr(logging, config.logging_config.level))
                
                with open(dataset_config.qa_path, "r") as f:
                    qa_pairs = json_repair.load(f)
                
                evaluator = Eval(config.api.llm_api_key)
                graphq = decomposer.GraphQ(dataset, config.api.llm_api_key, config=config)
                
                logging.info("🚀 Initializing retriever 🚀")
                logging.info("-"*30)
                
                kt_retriever = retriever.KTRetriever(
                    dataset, 
                    dataset_config.graph_output, 
                    recall_paths=config.retrieval.recall_paths,
                    llm_api_key=config.api.llm_api_key, 
                    schema_path=dataset_config.schema_path, 
                    top_k=config.retrieval.top_k_filter, 
                    mode=config.triggers.mode,
                    config=config
                )
                
                logging.info("🚀 Building FAISS index 🚀")
                logging.info("-"*30)
                start_time = time.time()
                kt_retriever.build_indices()
                logging.info(f"Time taken to build FAISS index: {time.time() - start_time} seconds")
                logging.info("-"*30)
                
                accuracy = 0
                total_time = 0
                total_questions = len(qa_pairs)
                logging.info(f"Start answering questions...")
                logging.info("-"*30)
            
                if config.triggers.mode == "noagent":
                    for qa in qa_pairs:
                        all_triples = set()
                        all_chunk_ids = set()
                        all_chunk_contents = dict()
                        all_sub_question_results = []

                    try:
                        decomposition_result = graphq.decompose(qa["question"], dataset_config.schema_path)
                        sub_questions = decomposition_result.get("sub_questions", [])
                        involved_types = decomposition_result.get("involved_types", {})
                        logging.info(f"Original question: {qa['question']}")
                        logging.info(f"Decomposed into {len(sub_questions)} sub-questions")
                        logging.info(f"Involved types: {involved_types}")
                    except Exception as e:
                        logging.error(f"Error decomposing question: {str(e)}")
                        sub_questions = [{"sub-question": qa["question"]}]
                        involved_types = {"nodes": [], "relations": [], "attributes": []}  

                    if len(sub_questions) > 1:
                        logging.info("🚀 Using parallel sub-question processing...")
                        start_time = time.time()
                        aggregated_results, parallel_time = kt_retriever.process_subquestions_parallel(
                            sub_questions, top_k=config.retrieval.top_k_filter, involved_types=involved_types
                        )
                        total_time += parallel_time
                        all_triples.update(aggregated_results['triples'])
                        all_chunk_ids.update(aggregated_results['chunk_ids'])
                        for chunk_id, content in aggregated_results['chunk_contents'].items():
                            all_chunk_contents[chunk_id] = content
                        all_sub_question_results = aggregated_results['sub_question_results']
                        logging.info(f"✅ Parallel processing completed in {parallel_time:.2f}s")

                    else:
                        logging.info("📝 Using single sub-question processing...")
                        for i, sub_question in enumerate(sub_questions):
                            try:
                                sub_question_text = sub_question["sub-question"]
                                logging.info(f"Processing sub-question {i+1}: {sub_question_text}")
                                retrieval_results, time_taken = kt_retriever.process_retrieval_results(sub_question_text, top_k=config.retrieval.top_k_filter, involved_types=involved_types)
                                print(retrieval_results)
                                total_time += time_taken
                                triples = retrieval_results.get('triples', []) or []
                                chunk_ids = retrieval_results.get('chunk_ids', []) or []
                                chunk_contents = retrieval_results.get('chunk_contents', []) or []
                                sub_result = {
                                    'sub_question': sub_question_text,
                                    'triples_count': len(triples),
                                    'chunk_ids_count': len(chunk_ids),
                                    'time_taken': time_taken
                                }
                                all_sub_question_results.append(sub_result)
                                all_triples.update(triples)
                                print(f"Debug: retrieval_results['chunk_ids'] = {chunk_ids}")
                                print(f"Debug: retrieval_results['chunk_contents'] = {chunk_contents}")
                                all_chunk_ids.update(chunk_ids)
                                if isinstance(chunk_contents, dict):
                                    for chunk_id, content in chunk_contents.items():
                                        all_chunk_contents[chunk_id] = content
                                else:
                                    for i, chunk_id in enumerate(chunk_ids):
                                        if i < len(chunk_contents):
                                            all_chunk_contents[chunk_id] = chunk_contents[i]
                                    else:
                                        print(f"Debug: Missing chunk content for chunk_id {chunk_id}")

                                logging.info(f"Sub-question {i+1} results: {len(retrieval_results['triples'])} triples, {len(retrieval_results['chunk_ids'])} chunks")

                            except Exception as e:
                                logging.error(f"Error processing sub-question {i+1}: {str(e)}")
                                sub_result = {
                                    'sub_question': sub_question_text,
                                    'triples_count': 0,
                                    'chunk_ids_count': 0,
                                    'time_taken': 0.0
                                }
                                all_sub_question_results.append(sub_result)
                                continue
                            
                    dedup_triples = deduplicate_triples(list(all_triples))
                    dedup_chunk_ids = list(set(all_chunk_ids))
                    dedup_chunk_contents = merge_chunk_contents(dedup_chunk_ids, all_chunk_contents)

                    if not dedup_triples and not dedup_chunk_contents:
                        logging.warning(f"No triples or chunks retrieved for question: {qa['question']}")
                        dedup_triples = ["No relevant information found"]
                        dedup_chunk_contents = ["No relevant chunks found"]

                    context = "=== Triples ===\n" + "\n".join(dedup_triples)
                    context += "\n=== Chunks ===\n" + "\n".join(dedup_chunk_contents)

                    if len(dedup_triples) > 20: 
                        question_keywords = set(qa["question"].lower().split())
                        scored_triples = []
                        for triple in dedup_triples:
                            triple_lower = triple.lower()
                            score = sum(1 for keyword in question_keywords if keyword in triple_lower)
                            scored_triples.append((triple, score))

                        scored_triples.sort(key=lambda x: x[1], reverse=True)
                        dedup_triples = [triple for triple, score in scored_triples[:config.retrieval.top_k_filter]]
                    
                    if len(dedup_chunk_contents) > config.retrieval.top_k_filter:
                        dedup_chunk_contents = rerank_chunks_by_keywords(dedup_chunk_contents, qa["question"], config.retrieval.top_k_filter)
                    
                    context = "=== Triples ===\n" + "\n".join(dedup_triples)
                    context += "\n=== Chunks ===\n" + "\n".join(dedup_chunk_contents)

                    for i, sub_result in enumerate(all_sub_question_results):
                        logging.info(f"  Sub-{i+1}: {sub_result['sub_question']} -> {sub_result['triples_count']} triples, {sub_result['chunk_ids_count']} chunks ({sub_result['time_taken']:.2f}s)")

                    prompt = kt_retriever.generate_prompt(qa["question"], context)

                    max_retries = 20
                    answer = None
                    for retry in range(max_retries):
                        try:
                            answer = kt_retriever.generate_answer(prompt, use_qwen=config.api.use_qwen)
                            if answer and answer.strip():
                                break
                        except Exception as e:
                            logging.error(f"Error generating answer (attempt {retry + 1}): {str(e)}")
                            if retry == max_retries - 1:
                                answer = "Error: Unable to generate answer"
                            time.sleep(1)

                    logging.info(f"========== Original Question: {qa['question']} ==========") 
                    logging.info(f"Gold Answer: {qa['answer']}")
                    logging.info(f"Generated Answer: {answer}")

                    logging.info("-"*30)

                    eval_result = evaluator.eval(qa["question"], qa["answer"], answer)
                    print(f"Eval result: {eval_result}")
                    if eval_result == "1":
                        accuracy += 1
                    logging.info(f"Eval result: {'Correct' if eval_result == '1' else 'Wrong'}")
                    logging.info(f"Overall Accuracy: {accuracy/total_questions*100}%")     
                    logging.info(f"Average time taken: {total_time/total_questions} seconds")
                
                elif config.triggers.mode == "agent":
                    max_steps = config.retrieval.agent.max_steps 
                    
                    for qa in qa_pairs:
                        step = 1
                        current_query = qa["question"]
                        thoughts = []
                        all_triples = set()
                        all_chunk_ids = set()
                        all_chunk_contents = dict()
                        logs = []
                        
                        logging.info(f"🚀 Starting IRCoT for question: {current_query}")
                        
                        retrieval_results, time_taken = kt_retriever.process_retrieval_results(current_query, top_k=config.retrieval.top_k_filter)
                        total_time += time_taken
                        
                        retrieved_triples = retrieval_results.get('triples', []) or []
                    retrieved_chunk_ids = retrieval_results.get('chunk_ids', []) or []
                    retrieved_chunk_contents = retrieval_results.get('chunk_contents', []) or []
                    
                    if isinstance(retrieved_chunk_contents, list):
                        chunk_contents_dict = {}
                        for i, chunk_id in enumerate(retrieved_chunk_ids):
                            if i < len(retrieved_chunk_contents):
                                chunk_contents_dict[chunk_id] = retrieved_chunk_contents[i]
                            else:
                                chunk_contents_dict[chunk_id] = f"[Missing content for chunk {chunk_id}]"
                    else:
                        chunk_contents_dict = retrieved_chunk_contents
                    
                    all_triples.update(retrieved_triples)
                    all_chunk_ids.update(retrieved_chunk_ids)
                    all_chunk_contents.update(chunk_contents_dict)
                    
                    while step <= max_steps:
                        logging.info(f"📝 IRCoT Step {step}/{max_steps}")
                        
                        dedup_triples = deduplicate_triples(list(all_triples))
                        dedup_chunk_ids = list(set(all_chunk_ids))
                        dedup_chunk_contents = merge_chunk_contents(dedup_chunk_ids, all_chunk_contents)
                        
                        context = "=== Triples ===\n" + "\n".join(dedup_triples)
                        context += "\n=== Chunks ===\n" + "\n".join(dedup_chunk_contents)
                        
                        ircot_prompt = f"""
                    You are an expert knowledge assistant using iterative retrieval with chain-of-thought reasoning.
                    
                    Current Question: {current_query}
                    
                    Available Knowledge Context:
                    {context}
                    
                    Previous Thoughts: {' '.join(thoughts) if thoughts else 'None'}
                    
                    Step {step}: Please think step by step about what additional information you need to answer the question completely and accurately.
                    
                    Instructions:
                    1. Analyze the current knowledge context and the question
                    2. Think about what information might be missing or unclear
                    3. If you have enough information to answer, in the end of your response, write "So the answer is:" followed by your final answer
                    4. If you need more information, in the end of your response, write a specific query begin with "The new query is:" to retrieve additional relevant information
                    5. Be specific and focused in your reasoning
                    
                    Your reasoning:
                    """
                        max_retries = 20
                        response = None
                        for retry in range(max_retries):
                            try:
                                response = kt_retriever.generate_answer(ircot_prompt, use_qwen=config.api.use_qwen)
                                if response and response.strip():
                                    break
                            except Exception as e:
                                logging.error(f"Error generating IRCoT response (attempt {retry + 1}): {str(e)}")
                                if retry == max_retries - 1:
                                    response = "Error: Unable to generate reasoning"
                                time.sleep(1)
                        
                        thoughts.append(response)
                        
                        logs.append({
                            "step": step,
                            "query": current_query,
                            "retrieved_triples_count": len(dedup_triples),
                            "retrieved_chunks_count": len(dedup_chunk_contents),
                            "response": response,
                            "thoughts": thoughts.copy()
                        })
                        
                        logging.info(f"Step {step} response: {response[:100]}...")
                        
                        if "So the answer is:" in response:
                            logging.info("✅ Final answer found, stopping IRCoT")
                            break

                        if "The new query is:" in response:
                            new_query = response.split("The new query is:")[1].strip()
                        else:
                            new_query = response
                        
                        if new_query and new_query != current_query:
                            current_query = new_query
                            logging.info(f"🔄 New query for next iteration: {current_query}")
                            
                            retrieval_results, time_taken = kt_retriever.process_retrieval_results(current_query, top_k=config.retrieval.top_k_filter)
                            total_time += time_taken
                            
                            new_triples = retrieval_results.get('triples', []) or []
                            new_chunk_ids = retrieval_results.get('chunk_ids', []) or []
                            new_chunk_contents = retrieval_results.get('chunk_contents', []) or []
                            
                            if isinstance(new_chunk_contents, list):
                                new_chunk_contents_dict = {}
                                for i, chunk_id in enumerate(new_chunk_ids):
                                    if i < len(new_chunk_contents):
                                        new_chunk_contents_dict[chunk_id] = new_chunk_contents[i]
                                    else:
                                        new_chunk_contents_dict[chunk_id] = f"[Missing content for chunk {chunk_id}]"
                            else:
                                new_chunk_contents_dict = new_chunk_contents
                            
                            all_triples.update(new_triples)
                            all_chunk_ids.update(new_chunk_ids)
                            all_chunk_contents.update(new_chunk_contents_dict)
                            
                            logging.info(f"Retrieved {len(new_triples)} new triples, {len(new_chunk_ids)} new chunks")
                        else:
                            logging.info("No new query generated, stopping IRCoT")
                            break
                        
                        step += 1
                    
                    final_context = "=== Final Triples ===\n" + "\n".join(deduplicate_triples(list(all_triples)))
                    final_context += "\n=== Final Chunks ===\n" + "\n".join(merge_chunk_contents(list(set(all_chunk_ids)), all_chunk_contents))
                    
                    final_prompt = kt_retriever.generate_prompt(qa["question"], final_context)
                    
                    max_retries = 20
                    answer = None
                    for retry in range(max_retries):
                        try:
                            answer = kt_retriever.generate_answer(final_prompt, use_qwen=config.api.use_qwen)
                            if answer and answer.strip():
                                break
                        except Exception as e:
                            logging.error(f"Error generating final answer (attempt {retry + 1}): {str(e)}")
                            if retry == max_retries - 1:
                                answer = "Error: Unable to generate answer"
                            time.sleep(1)
                    
                    logging.info(f"========== Original Question: {qa['question']} ==========") 
                    logging.info(f"IRCoT Steps: {len(thoughts)}")
                    logging.info(f"Final Triples: {len(deduplicate_triples(list(all_triples)))}")
                    logging.info(f"Final Chunks: {len(merge_chunk_contents(list(set(all_chunk_ids)), all_chunk_contents))}")
                    logging.info(f"Gold Answer: {qa['answer']}")
                    logging.info(f"Generated Answer: {answer}")
                    logging.info(f"Thought Process: {' | '.join(thoughts)}")
                    
                    logging.info("-"*30)
                    
                    eval_result = evaluator.eval(qa["question"], qa["answer"], answer)
                    print(f"Eval result: {eval_result}")
                    if eval_result == "1":
                        accuracy += 1
                    logging.info(f"Eval result: {'Correct' if eval_result == '1' else 'Wrong'}")
                    
                    logging.info(f"Overall Accuracy: {accuracy/total_questions*100}%")     
                    logging.info(f"Average time taken: {total_time/total_questions} seconds")
                
            except Exception as e:
                logging.error(f"Failed to process dataset {dataset}: {e}")
                continue