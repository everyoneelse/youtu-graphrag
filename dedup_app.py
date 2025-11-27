"""
Streamlit Deduplication App - Multi-stage Knowledge Graph Deduplication

This app provides a multi-stage deduplication workflow for knowledge graphs:
1. Alias relationship deduplication
2. Tail entity deduplication
3. Head entity deduplication
4. Final tail entity deduplication

Each stage provides downloadable results and intermediate outputs.
"""

import streamlit as st
import asyncio
import time
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import base64
from datetime import datetime
import traceback
import copy

# Import existing modules
from offline_semantic_dedup import (
    OfflineSemanticDeduper,
    dedup_alias_relationships,
    _load_chunk_mapping
)
from config import ConfigManager, get_config
from apply_tail_dedup_results import apply_entity_dedup_results_to_graph, TailDedupApplicator
from utils_ import graph_processor
from utils_.logger import logger



def setup_page_config():
    """Setup page configuration"""
    st.set_page_config(
        page_title="知识图谱去重工具",
        page_icon="",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def display_header():
    """Display application header"""
    st.title("知识图谱去重工具")
    st.markdown("多阶段去重流程，支持下载中间结果")


def keep_alive():
    """Keep the session alive by updating last activity timestamp"""
    current_time = time.time()
    st.session_state.last_activity = current_time

    # Display connection status (hidden in an expander)
    with st.expander("🔗 连接状态", expanded=False):
        elapsed = current_time - st.session_state.get('last_activity', current_time)
        st.write(f"最后活动时间: {time.strftime('%H:%M:%S', time.localtime(current_time))}")
        st.write(f"连接状态: ✅ 活跃")

        # Add a refresh button
        if st.button("刷新连接", key="keep_alive_refresh"):
            st.rerun()


def initialize_session_state():
    """Initialize session state variables"""
    if 'current_stage' not in st.session_state:
        st.session_state.current_stage = 0

    if 'stages_completed' not in st.session_state:
        st.session_state.stages_completed = []

    if 'graph' not in st.session_state:
        st.session_state.graph = None

    if 'chunk_data' not in st.session_state:
        st.session_state.chunk_data = None

    if 'dedup_results' not in st.session_state:
        st.session_state.dedup_results = {}

    if 'processing' not in st.session_state:
        st.session_state.processing = False

    if 'progress' not in st.session_state:
        st.session_state.progress = 0

    if 'status_message' not in st.session_state:
        st.session_state.status_message = "准备开始去重"

    if 'skipped_stages' not in st.session_state:
        st.session_state.skipped_stages = []
    elif not isinstance(st.session_state.skipped_stages, list):
        # Ensure it's always a list
        st.session_state.skipped_stages = []

    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = time.time()


def reset_session_state():
    """Force reset all session state variables to initial values and clear saved state"""
    # Reset all session state variables to initial values
    st.session_state.current_stage = 0
    st.session_state.stages_completed = []
    st.session_state.graph = None
    st.session_state.chunk_data = None
    st.session_state.dedup_results = {}
    st.session_state.processing = False
    st.session_state.progress = 0
    st.session_state.status_message = "准备开始去重"
    st.session_state.skipped_stages = []
    st.session_state.last_activity = time.time()

    # Clear any additional variables that may have been added
    keys_to_remove = [
        'uploaded_graph_name', 'session_id', 'workflow_id',
        'workflow_log_dir', 'session_log_dir', 'stage_start_time',
        'last_error', 'last_state_save', 'clear_error_requested'
    ]

    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]

    # Delete saved session state file to prevent restoration of old results
    try:
        session_id = os.environ.get('DEDUPLICATION_SESSION_ID', f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        session_log_dir = Path("logs") / session_id
        state_file = session_log_dir / "session_state.json"

        if state_file.exists():
            state_file.unlink()
            logger.info(f"Deleted saved session state file: {state_file}")

        # Also try to delete any workflow-specific state files
        if hasattr(st.session_state, 'workflow_log_dir') and st.session_state.workflow_log_dir:
            workflow_state_file = Path(st.session_state.workflow_log_dir) / "session_state.json"
            if workflow_state_file.exists():
                workflow_state_file.unlink()
                logger.info(f"Deleted workflow session state file: {workflow_state_file}")

    except Exception as e:
        logger.warning(f"Failed to delete saved session state files: {e}")

    logger.info("Session state fully reset, including saved files")


def create_download_link(data: Any, filename: str, mime_type: str = "application/json") -> str:
    """Create a download link for data"""
    if isinstance(data, (dict, list)):
        data_str = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        data_str = str(data)

    b64 = base64.b64encode(data_str.encode()).decode()
    href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}" style="color: white; background: #007bff; padding: 8px 16px; border-radius: 5px; text-decoration: none; display: inline-block; margin: 5px;">下载 {filename}</a>'
    return href




def display_workflow_stages():
    """Display the workflow stages with status"""
    stages = [
        {"name": "阶段1: 别名去重", "desc": "使用'别名包括'关系进行去重"},
        {"name": "阶段2: 尾实体去重", "desc": "语义去重尾实体"},
        {"name": "阶段3: 头实体去重", "desc": "语义去重头实体"},
        {"name": "阶段4: 最终尾实体去重", "desc": "最终清理尾实体"}
    ]

    st.markdown("### 去重流程阶段")

    cols = st.columns(len(stages))
    for i, stage in enumerate(stages):
        with cols[i]:
            stage_names = ["别名去重", "尾实体去重",
                          "头实体去重", "最终尾实体去重"]
            stage_name = stage_names[i]

            # Check if this stage was skipped
            was_skipped = (hasattr(st.session_state, 'skipped_stages') and
                          stage_name in st.session_state.skipped_stages)

            if i < st.session_state.current_stage:
                if was_skipped:
                    st.warning(f'**{stage["name"]}**\n\n{stage["desc"]}\n\n已跳过')
                else:
                    st.success(f'**{stage["name"]}**\n\n{stage["desc"]}\n\n已完成')
            elif i == st.session_state.current_stage and st.session_state.processing:
                st.warning(f'**{stage["name"]}**\n\n{stage["desc"]}\n\n处理中')
            else:
                st.info(f'**{stage["name"]}**\n\n{stage["desc"]}\n\n等待中')


def display_progress_section():
    """Display progress section with enhanced feedback"""
    if st.session_state.processing or st.session_state.progress > 0:
        st.markdown("### 处理进度")

        # Progress bar
        progress_bar = st.progress(st.session_state.progress)

        # Status message with timestamp
        status_text = st.empty()
        current_time = time.strftime("%H:%M:%S", time.localtime())
        status_with_time = f"**{st.session_state.status_message}** (更新时间: {current_time})"
        status_text.markdown(status_with_time)

        # Additional status information
        col1, col2, col3 = st.columns(3)

        with col1:
            stage_names = ["准备", "别名去重", "尾实体去重", "头实体去重", "最终尾实体去重"]
            current_stage_name = stage_names[min(st.session_state.current_stage, len(stage_names)-1)]
            st.info(f"当前阶段: {current_stage_name}")

        with col2:
            elapsed_time = time.time() - getattr(st.session_state, 'stage_start_time', time.time())
            st.info(f"已用时间: {int(elapsed_time)}秒")

        with col3:
            if st.session_state.processing:
                st.warning("⚡ 处理中，请勿关闭页面")
            else:
                st.success("✅ 就绪")

        # Error handling and recovery options
        if hasattr(st.session_state, 'last_error') and st.session_state.last_error:
            st.error(f"上次错误: {st.session_state.last_error}")
            if st.button("清除错误并重试", key="clear_error_retry"):
                # Set flag instead of direct modification
                st.session_state.clear_error_requested = True

        return progress_bar, status_text

    return None, None


def display_results_section():
    """Display results and download section"""
    if st.session_state.stages_completed:
        st.markdown("### 结果下载")

        for stage_name in st.session_state.stages_completed:
            if stage_name in st.session_state.dedup_results:
                stage_data = st.session_state.dedup_results[stage_name]

                # Check if stage was skipped
                is_skipped = stage_data.get('skipped', False)
                expander_title = f"{stage_name} 结果 (已跳过)" if is_skipped else f"{stage_name} 结果"

                with st.expander(expander_title, expanded=False):
                    if is_skipped:
                        st.info("此阶段已被跳过，没有执行去重操作")
                        col1, col2 = st.columns(2)

                        # Graph stats (unchanged from previous stage)
                        if 'graph_stats' in stage_data:
                            with col1:
                                stats_info = f"节点数: {stage_data['graph_stats'].get('nodes', 'N/A')}, 边数: {stage_data['graph_stats'].get('edges', 'N/A')}"
                                st.info(f"图统计: {stats_info}")

                        with col2:
                            st.info("去重结果: 无 (已跳过)")
                    else:
                        # Get uploaded graph name for filename
                        uploaded_graph_name = getattr(st.session_state, 'uploaded_graph_name', 'graph')
                        # Remove .json extension if present for cleaner naming
                        base_name = uploaded_graph_name.replace('.json', '')

                        col1, col2, col3 = st.columns(3)

                        # Deduplication results
                        if 'dedup_results' in stage_data:
                            with col1:
                                # Map Chinese stage names to English filenames with graph name
                                stage_filename_map = {
                                    "别名去重": f"{base_name}_alias_dedup_results.json",
                                    "尾实体去重": f"{base_name}_tail_entity_dedup_results.json",
                                    "头实体去重": f"{base_name}_head_entity_dedup_results.json",
                                    "最终尾实体去重": f"{base_name}_final_tail_dedup_results.json"
                                }
                                filename = stage_filename_map.get(stage_name, f"{base_name}_{stage_name}_dedup_results.json")
                                st.markdown(
                                    create_download_link(
                                        stage_data['dedup_results'],
                                        filename
                                    ),
                                    unsafe_allow_html=True
                                )

                        # Graph after deduplication
                        if 'graph_stats' in stage_data:
                            with col2:
                                stats_info = f"节点数: {stage_data['graph_stats'].get('nodes', 'N/A')}, 边数: {stage_data['graph_stats'].get('edges', 'N/A')}"
                                st.info(f"图统计: {stats_info}")

                        # Download deduplicated graph
                        if st.session_state.graph is not None:
                            with col3:
                                # Map Chinese stage names to graph filenames
                                stage_graph_filename_map = {
                                    "别名去重": f"{base_name}_after_alias_dedup.json",
                                    "尾实体去重": f"{base_name}_after_tail_entity_dedup.json",
                                    "头实体去重": f"{base_name}_after_head_entity_dedup.json",
                                    "最终尾实体去重": f"{base_name}_after_final_tail_dedup.json"
                                }
                                graph_filename = stage_graph_filename_map.get(stage_name, f"{base_name}_{stage_name}_dedup_graph.json")

                                # Create temporary file to get JSON string
                                import tempfile
                                import os

                                with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
                                    temp_path = temp_file.name
                                    graph_processor.save_graph_to_json(st.session_state.graph, temp_path)

                                    # Read the JSON content
                                    with open(temp_path, 'r', encoding='utf-8') as f:
                                        graph_json_str = f.read()

                                    # Clean up temp file
                                    os.unlink(temp_path)

                                st.markdown(
                                    create_download_link(
                                        graph_json_str,
                                        graph_filename
                                    ),
                                    unsafe_allow_html=True
                                )


def update_progress(progress: int, message: str):
    """Update progress callback"""
    st.session_state.progress = progress
    st.session_state.status_message = message


async def run_deduplication_stage(stage_name: str, stage_func):
    """Run a deduplication stage asynchronously with enhanced error handling"""
    try:
        st.session_state.processing = True
        st.session_state.status_message = f"开始 {stage_name}..."
        st.session_state.stage_start_time = time.time()
        st.session_state.last_error = None

        # Save state before starting
        save_session_state()

        # Run the deduplication function
        result = await stage_func()

        # Store results
        st.session_state.dedup_results[stage_name] = result
        st.session_state.stages_completed.append(stage_name)
        st.session_state.current_stage += 1

        st.session_state.status_message = f"{stage_name} 成功完成!"
        st.session_state.progress = 100

        # Save successful state immediately after updating
        save_session_state()

        # Brief pause to show completion
        time.sleep(1)

        # Force UI refresh to show updated state
        st.rerun()

    except Exception as e:
        error_msg = f"{stage_name} 出现错误: {str(e)}"
        st.session_state.last_error = error_msg
        st.session_state.status_message = f"{stage_name} 失败 - 查看错误详情"
        st.error(error_msg)

        # Save error state for recovery
        save_session_state()

        logger.error(f"Stage {stage_name} failed: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
    finally:
        st.session_state.processing = False




async def stage_1_alias_dedup():
    """Stage 1: Alias relationship deduplication"""
    update_progress(10, "分析别名关系...")

    # Run alias deduplication
    alias_results = dedup_alias_relationships(st.session_state.graph)

    update_progress(50, "应用别名去重到图...")

    # Apply results to graph
    if alias_results:
        st.session_state.graph = apply_entity_dedup_results_to_graph(
            st.session_state.graph, alias_results
        )

    update_progress(90, "保存别名去重结果...")

    # Collect results
    result = {
        'dedup_results': alias_results,
        'graph_stats': {
            'nodes': st.session_state.graph.number_of_nodes(),
            'edges': st.session_state.graph.number_of_edges()
        }
    }

    return result


async def stage_2_tail_entity_dedup():
    """Stage 2: Tail entity semantic deduplication"""
    logger = logging.getLogger(__name__)

    # Setup stage-specific logging
    if hasattr(st.session_state, 'workflow_log_dir'):
        stage_log_path = st.session_state.workflow_log_dir / "stage_2_tail_entity_dedup.log"
        stage_handler = logging.FileHandler(stage_log_path, encoding='utf-8')
        stage_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(stage_handler)
        logger.info(f"Starting Stage 2: Tail entity semantic deduplication - Session: {st.session_state.session_id}, Workflow: {st.session_state.workflow_id}")

    update_progress(10, "初始化尾实体去重...")
    logger.info("Initializing tail entity deduplication")

    config = get_config()
    deduper = OfflineSemanticDeduper(config, dataset_name="ui_dedup_session", log_dir=st.session_state.workflow_log_dir)
    deduper.graph = st.session_state.graph
    deduper.ori_graph = copy.deepcopy(st.session_state.graph)
    deduper.all_chunks = st.session_state.chunk_data
    logger.info(f"Loaded graph with {deduper.graph.number_of_nodes()} nodes and {deduper.graph.number_of_edges()} edges")

    update_progress(30, "运行尾实体语义去重...")
    logger.info("Running tail entity semantic deduplication")

    # Run tail entity deduplication
    dedup_results = deduper.triple_deduplicate_semantic(return_dedup_results=True)
    logger.info(f"Tail entity deduplication completed, found {len(dedup_results) if dedup_results else 0} deduplication groups")

    update_progress(70, "应用去重结果...")
    logger.info("Applying deduplication results")

    if dedup_results:
        deduper.graph = apply_entity_dedup_results_to_graph(deduper.graph, dedup_results)
        st.session_state.graph = deduper.graph
        logger.info("Deduplication results applied successfully")

    update_progress(90, "收集结果...")
    logger.info("Collecting final results")

    result = {
        'dedup_results': dedup_results,
        'graph_stats': {
            'nodes': st.session_state.graph.number_of_nodes(),
            'edges': st.session_state.graph.number_of_edges()
        }
    }

    logger.info(f"Stage 2 completed. Final graph: {result['graph_stats']['nodes']} nodes, {result['graph_stats']['edges']} edges")
    return result


async def stage_3_head_entity_dedup():
    """Stage 3: Head entity deduplication"""
    logger = logging.getLogger(__name__)

    # Setup stage-specific logging
    if hasattr(st.session_state, 'workflow_log_dir'):
        stage_log_path = st.session_state.workflow_log_dir / "stage_3_head_entity_dedup.log"
        stage_handler = logging.FileHandler(stage_log_path, encoding='utf-8')
        stage_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(stage_handler)
        logger.info(f"Starting Stage 3: Head entity deduplication - Session: {st.session_state.session_id}, Workflow: {st.session_state.workflow_id}")

    update_progress(10, "初始化头实体去重...")
    logger.info("Initializing head entity deduplication")

    config = get_config()
    deduper = OfflineSemanticDeduper(config, dataset_name="ui_dedup_session", log_dir=st.session_state.workflow_log_dir)
    deduper.graph = st.session_state.graph
    deduper.ori_graph = copy.deepcopy(st.session_state.graph)
    deduper.all_chunks = st.session_state.chunk_data
    logger.info(f"Loaded graph with {deduper.graph.number_of_nodes()} nodes and {deduper.graph.number_of_edges()} edges")

    update_progress(30, "运行头实体去重...")
    logger.info("Running head entity deduplication")

    # Run head entity deduplication
    head_dedup_results = deduper.deduplicate_heads_with_llm_v2(
        load_llm_results=False,
        return_dedup_results=True
    )
    logger.info(f"Head entity deduplication completed, found {len(head_dedup_results) if head_dedup_results else 0} deduplication groups")

    update_progress(70, "应用头实体去重结果...")
    logger.info("Applying head entity deduplication results")

    if head_dedup_results:
        deduper.graph = apply_entity_dedup_results_to_graph(deduper.graph, head_dedup_results)
        st.session_state.graph = deduper.graph
        logger.info("Head entity deduplication results applied successfully")

    update_progress(90, "收集结果...")
    logger.info("Collecting final results")

    result = {
        'dedup_results': head_dedup_results or [],
        'graph_stats': {
            'nodes': st.session_state.graph.number_of_nodes(),
            'edges': st.session_state.graph.number_of_edges()
        }
    }

    logger.info(f"Stage 3 completed. Final graph: {result['graph_stats']['nodes']} nodes, {result['graph_stats']['edges']} edges")
    return result


async def stage_4_final_tail_dedup():
    """Stage 4: Final tail entity deduplication"""
    logger = logging.getLogger(__name__)

    # Setup stage-specific logging
    if hasattr(st.session_state, 'workflow_log_dir'):
        stage_log_path = st.session_state.workflow_log_dir / "stage_4_final_tail_dedup.log"
        stage_handler = logging.FileHandler(stage_log_path, encoding='utf-8')
        stage_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(stage_handler)
        logger.info(f"Starting Stage 4: Final tail entity deduplication - Session: {st.session_state.session_id}, Workflow: {st.session_state.workflow_id}")

    update_progress(10, "初始化最终尾实体去重...")
    logger.info("Initializing final tail entity deduplication")

    config = get_config()
    deduper = OfflineSemanticDeduper(config, dataset_name="ui_dedup_session", log_dir=st.session_state.workflow_log_dir)
    deduper.graph = st.session_state.graph
    deduper.ori_graph = copy.deepcopy(st.session_state.graph)
    deduper.all_chunks = st.session_state.chunk_data
    logger.info(f"Loaded graph with {deduper.graph.number_of_nodes()} nodes and {deduper.graph.number_of_edges()} edges")

    update_progress(30, "运行最终语义去重...")
    logger.info("Running final tail entity semantic deduplication")

    # Run final tail deduplication
    #final_dedup_results = deduper.triple_deduplicate_semantic(return_dedup_results=True)
    #logger.info(f"Final tail entity deduplication completed, found {len(final_dedup_results) if final_dedup_results else 0} deduplication groups")

    merged_head_ids = set()
    head_dedup_result = st.session_state.dedup_results.get("头实体去重", {})
    head_dedup_groups = head_dedup_result.get("dedup_results") if isinstance(head_dedup_result, dict) else []

    if head_dedup_groups:
        applicator = TailDedupApplicator(st.session_state.graph)
        for group in head_dedup_groups:
            dedup_clusters = group.get("dedup_results", {})
            for cluster_data in dedup_clusters.values():
                members = cluster_data.get("member", [])
                if len(members) < 2:
                    continue
                representative_id = applicator._find_node_by_identifier(members[-1])
                if representative_id:
                    merged_head_ids.add(representative_id)

    if not merged_head_ids:
        logger.info("No head entities were merged in Stage 3; skipping final tail deduplication.")
        return {
            'dedup_results': [],
            'graph_stats': {
                'nodes': st.session_state.graph.number_of_nodes(),
                'edges': st.session_state.graph.number_of_edges()
            }
        }

    # Run final tail deduplication only for merged head entities
    final_dedup_results = deduper.triple_deduplicate_semantic(
        return_dedup_results=True,
        target_heads=merged_head_ids
    )
    logger.info(
        "Final tail entity deduplication completed, found %d deduplication groups",
        len(final_dedup_results) if final_dedup_results else 0
    )

    update_progress(70, "应用最终去重结果...")
    logger.info("Applying final deduplication results")

    if final_dedup_results:
        deduper.graph = apply_entity_dedup_results_to_graph(deduper.graph, final_dedup_results)
        st.session_state.graph = deduper.graph
        logger.info("Final deduplication results applied successfully")

    update_progress(90, "完成结果处理...")
    logger.info("Collecting final results")

    result = {
        'dedup_results': final_dedup_results or [],
        'graph_stats': {
            'nodes': st.session_state.graph.number_of_nodes(),
            'edges': st.session_state.graph.number_of_edges()
        }
    }

    logger.info(f"Stage 4 completed. Final graph: {result['graph_stats']['nodes']} nodes, {result['graph_stats']['edges']} edges")
    return result


def run_stage(stage_num: int):
    """Run a specific deduplication stage"""
    stage_functions = {
        1: stage_1_alias_dedup,
        2: stage_2_tail_entity_dedup,
        3: stage_3_head_entity_dedup,
        4: stage_4_final_tail_dedup
    }

    stage_names = {
        1: "别名去重",
        2: "尾实体去重",
        3: "头实体去重",
        4: "最终尾实体去重"
    }

    if stage_num in stage_functions:
        asyncio.run(run_deduplication_stage(
            stage_names[stage_num],
            stage_functions[stage_num]
        ))


def skip_stage(stage_num: int):
    """Skip a specific deduplication stage"""
    stage_names = {
        1: "别名去重",
        2: "尾实体去重",
        3: "头实体去重",
        4: "最终尾实体去重"
    }

    stage_name = stage_names.get(stage_num, f"Stage {stage_num}")

    logger.info(f"Skipping stage {stage_num}: {stage_name}, current_stage before: {st.session_state.current_stage}")

    try:
        st.session_state.processing = True
        st.session_state.status_message = f"跳过 {stage_name}..."

        # Record the skipped stage
        if stage_name not in st.session_state.skipped_stages:
            st.session_state.skipped_stages.append(stage_name)
            logger.info(f"Added {stage_name} to skipped_stages: {st.session_state.skipped_stages}")

        # Create empty results for skipped stage (to maintain workflow continuity)
        skipped_result = {
            'dedup_results': [],
            'graph_stats': {
                'nodes': st.session_state.graph.number_of_nodes() if st.session_state.graph else 0,
                'edges': st.session_state.graph.number_of_edges() if st.session_state.graph else 0
            },
            'skipped': True
        }

        # Store results (empty for skipped stage)
        st.session_state.dedup_results[stage_name] = skipped_result
        st.session_state.stages_completed.append(stage_name)
        st.session_state.current_stage += 1

        logger.info(f"Stage {stage_name} skipped successfully. current_stage after: {st.session_state.current_stage}, stages_completed: {st.session_state.stages_completed}")

        # Save the updated state immediately
        save_session_state()

        st.session_state.status_message = f"{stage_name} 成功跳过!"
        st.session_state.progress = 100

        # Brief pause to show completion
        time.sleep(0.5)

        # Force UI refresh to show updated state
        st.rerun()

    except Exception as e:
        error_msg = f"跳过 {stage_name} 时出现错误: {str(e)}"
        st.error(error_msg)
        logger.error(f"Stage {stage_name} skip failed: {str(e)}\n{traceback.format_exc()}")
    finally:
        st.session_state.processing = False


def file_upload_section():
    """File upload section"""
    st.markdown("### 输入文件")

    col1, col2 = st.columns(2)

    with col1:
        graph_file = st.file_uploader(
            "上传知识图谱JSON文件",
            type=["json"],
            help="上传需要去重的知识图谱文件"
        )

    with col2:
        chunk_file = st.file_uploader(
            "上传Chunks数据",
            type=["txt", "json"],
            help="上传用于语义去重的数据Chunks文件"
        )

    if graph_file and chunk_file:
        if st.button("加载并开始去重", type="primary", use_container_width=True):
            try:
                # Setup logging
                logger = logging.getLogger(__name__)

                # Create uploaded_files directory if it doesn't exist
                upload_dir = Path("uploaded_files")
                upload_dir.mkdir(exist_ok=True)

                # Generate timestamp for unique filenames
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # Save graph file permanently
                graph_filename = f"{timestamp}_graph_{graph_file.name}"
                graph_filepath = upload_dir / graph_filename

                logger.info(f"Saving uploaded graph file: {graph_filepath}")
                graph_data = json.load(graph_file)
                with open(graph_filepath, 'w', encoding='utf-8') as f:
                    json.dump(graph_data, f, ensure_ascii=False, indent=2)

                # Save chunk file permanently
                chunk_filename = f"{timestamp}_chunk_{chunk_file.name}"
                chunk_filepath = upload_dir / chunk_filename

                logger.info(f"Saving uploaded chunk file: {chunk_filepath}")
                if chunk_file.name.endswith('.json'):
                    chunk_data = json.load(chunk_file)
                    st.session_state.chunk_data = chunk_data
                    with open(chunk_filepath, 'w', encoding='utf-8') as f:
                        json.dump(chunk_data, f, ensure_ascii=False, indent=2)
                else:
                    # Assume text format
                    content = chunk_file.getvalue().decode('utf-8')
                    st.session_state.chunk_data = _load_chunk_mapping_from_content(content)
                    with open(chunk_filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                # Load graph
                st.session_state.graph = graph_processor.load_graph_from_json(str(graph_filepath))

                logger.info(f"Successfully loaded graph with {st.session_state.graph.number_of_nodes()} nodes and {st.session_state.graph.number_of_edges()} edges")
                logger.info(f"Files saved to: {graph_filepath} and {chunk_filepath}")

                # Save uploaded filenames for download naming
                st.session_state.uploaded_graph_name = graph_file.name

                st.success("文件加载成功！准备开始去重。")
                st.session_state.current_stage = 0
                st.session_state.stages_completed = []
                st.session_state.dedup_results = {}

            except Exception as e:
                logger.error(f"Error loading files: {str(e)}")
                st.error(f"加载文件时出现错误: {str(e)}")


def _load_chunk_mapping_from_content(content: str) -> Dict[str, str]:
    """Load chunk mapping from text content"""
    chunk_map = {}
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        if '\t' in line:
            prefix, chunk_part = line.split('\t', 1)
            if prefix.startswith("id: "):
                chunk_id = prefix[4:].strip()
            if chunk_part.startswith("Chunk: "):
                chunk_text = chunk_part[7:].strip()
                if chunk_id and chunk_text:
                    chunk_map[chunk_id] = chunk_text
    return chunk_map




def control_panel():
    """Control panel for starting stages"""
    if st.session_state.graph is not None and st.session_state.chunk_data is not None:
        st.markdown("### 控制面板")

        # Debug info
        st.write(f"Debug - 当前阶段: {st.session_state.current_stage}, 已完成阶段: {len(st.session_state.stages_completed) if hasattr(st.session_state, 'stages_completed') else 0}")

        # Control buttons in columns
        if st.session_state.current_stage < 4:
            # Show current stage info
            stage_names = ["别名去重", "尾实体去重", "头实体去重", "最终尾实体去重"]
            if st.session_state.current_stage < len(stage_names):
                current_stage_name = stage_names[st.session_state.current_stage]
            else:
                current_stage_name = f"阶段 {st.session_state.current_stage + 1}"
            col1, col2 = st.columns(2)

            with col1:
                if st.button(f"开始 {current_stage_name}", type="primary", use_container_width=True):
                    logger.info(f"Starting stage {st.session_state.current_stage + 1}: {current_stage_name}")
                    run_stage(st.session_state.current_stage + 1)

            with col2:
                if st.button(f"跳过 {current_stage_name}", use_container_width=True):
                    logger.info(f"Skipping stage {st.session_state.current_stage + 1}: {current_stage_name}")
                    skip_stage(st.session_state.current_stage + 1)
        else:
            st.success("所有去重阶段已完成！")

        # Show skipped stages if any
        if hasattr(st.session_state, 'skipped_stages') and st.session_state.skipped_stages:
            st.info(f"跳过阶段: {', '.join(st.session_state.skipped_stages)}")

        # Reset button
        if st.button("重置工作流", use_container_width=True):
            # Force reset all session state variables
            reset_session_state()


def main():
    """Main application function"""
    # Handle recovery actions from query parameters (must be done before any rendering)
    if st.query_params.get("restart_stage") == "true":
        st.query_params.clear()
        # Reset processing state but keep other data
        st.session_state.processing = False
        st.session_state.progress = 0
        st.session_state.status_message = "准备重新开始"
        # Clear stage timing
        if hasattr(st.session_state, 'stage_start_time'):
            del st.session_state.stage_start_time
        if hasattr(st.session_state, 'last_error'):
            del st.session_state.last_error

    if st.query_params.get("skip_stage") == "true":
        st.query_params.clear()
        # Reset processing state
        st.session_state.processing = False
        st.session_state.progress = 0
        st.session_state.status_message = "已跳过当前阶段"
        # Clear stage timing
        if hasattr(st.session_state, 'stage_start_time'):
            del st.session_state.stage_start_time
        if hasattr(st.session_state, 'last_error'):
            del st.session_state.last_error

        # Get stage info for skip operation
        stage_names = ["别名去重", "尾实体去重", "头实体去重", "最终尾实体去重"]
        current_stage_idx = st.session_state.current_stage
        if current_stage_idx < len(stage_names):
            # Perform skip operation safely
            stage_name = stage_names[current_stage_idx]

            # Record the skipped stage
            if stage_name not in st.session_state.skipped_stages:
                st.session_state.skipped_stages.append(stage_name)

            # Create empty results for skipped stage (to maintain workflow continuity)
            skipped_result = {
                'dedup_results': [],
                'graph_stats': {
                    'nodes': st.session_state.graph.number_of_nodes() if st.session_state.graph else 0,
                    'edges': st.session_state.graph.number_of_edges() if st.session_state.graph else 0
                },
                'skipped': True
            }

            # Store results (empty for skipped stage)
            st.session_state.dedup_results[stage_name] = skipped_result
            st.session_state.stages_completed.append(stage_name)
            st.session_state.current_stage += 1

            # Save the updated state
            save_session_state()

    # Get session info from environment variables set by run_dedup_ui.py
    session_id = os.environ.get('DEDUPLICATION_SESSION_ID', f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    session_log_dir = os.environ.get('DEDUPLICATION_LOG_DIR', str(Path("logs") / session_id))

    # Generate workflow ID for this session
    workflow_id = f"workflow_{datetime.now().strftime('%H%M%S')}"

    # Setup logging with session and workflow-based organization
    session_log_path = Path(session_log_dir)
    workflow_log_dir = session_log_path / workflow_id
    workflow_log_dir.mkdir(parents=True, exist_ok=True)

    log_filename = f"ui_app.log"
    log_path = workflow_log_dir / log_filename

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Graph Deduplication UI Application - Session: {session_id}, Workflow: {workflow_id}")

    # Setup page config FIRST (must be the first Streamlit command)
    setup_page_config()

    # Initialize session state
    initialize_session_state()

    # Store workflow info in session state for use throughout the app
    st.session_state.session_id = session_id
    st.session_state.workflow_id = workflow_id
    st.session_state.workflow_log_dir = workflow_log_dir
    st.session_state.session_log_dir = session_log_path

    # Try to restore previous session state
    restore_session_state(session_id)

    display_header()
    keep_alive()
    auto_save_session_state()

    # Check for recovery options
    check_and_display_recovery_options()

    # Main content
    file_upload_section()

    if st.session_state.graph is not None:
        display_workflow_stages()
        display_progress_section()
        control_panel()
        display_results_section()


def get_widget_keys():
    """Get list of widget keys that should not be saved/restored"""
    return [
        'keep_alive_refresh',
        # Add other widget keys here as needed
    ]

def save_session_state():
    """Save current session state to disk for recovery"""
    try:
        if hasattr(st.session_state, 'session_log_dir') and st.session_state.session_log_dir:
            state_file = st.session_state.session_log_dir / "session_state.json"

            # Create a copy of session state excluding non-serializable objects and widget keys
            state_to_save = {}
            widget_keys = get_widget_keys()

            for key in st.session_state:
                # Skip complex objects that can't be serialized
                if key in ['graph', 'chunk_data', 'workflow_log_dir', 'session_log_dir']:
                    continue
                # Skip widget keys that would cause conflicts
                if key in widget_keys:
                    continue
                try:
                    # Test if the value is JSON serializable
                    json.dumps(st.session_state[key])
                    state_to_save[key] = st.session_state[key]
                except (TypeError, ValueError):
                    # Skip non-serializable values
                    continue

            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_to_save, f, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        logger.error(f"Failed to save session state: {e}")


def restore_session_state(session_id):
    """Restore session state from disk"""
    try:
        session_log_dir = Path("logs") / session_id
        state_file = session_log_dir / "session_state.json"

        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                saved_state = json.load(f)

            # Widget keys that should not be restored
            widget_keys = get_widget_keys()

            # Restore serializable state values with proper type conversion
            for key, value in saved_state.items():
                if key not in ['graph', 'chunk_data', 'workflow_log_dir', 'session_log_dir'] and key not in widget_keys:
                    # Ensure proper types for critical session state variables
                    if key == 'current_stage' and isinstance(value, str):
                        # Convert string to int for current_stage
                        try:
                            st.session_state[key] = int(value)
                        except ValueError:
                            st.session_state[key] = 0  # Default to 0 if conversion fails
                    elif key == 'progress' and isinstance(value, str):
                        # Convert string to float for progress
                        try:
                            st.session_state[key] = float(value)
                        except ValueError:
                            st.session_state[key] = 0.0  # Default to 0.0 if conversion fails
                    elif key in ['processing'] and isinstance(value, str):
                        # Convert string booleans back to bool
                        st.session_state[key] = value.lower() == 'true'
                    elif key in ['skipped_stages', 'stages_completed'] and isinstance(value, str):
                        # Convert string lists back to lists (if saved as strings)
                        try:
                            st.session_state[key] = json.loads(value) if value else []
                        except (json.JSONDecodeError, TypeError):
                            st.session_state[key] = value if isinstance(value, list) else []
                    else:
                        st.session_state[key] = value

            logger.info(f"Restored session state from {state_file}")
            logger.info(f"Restored values: current_stage={st.session_state.get('current_stage', 'N/A')}, processing={st.session_state.get('processing', 'N/A')}, skipped_stages={st.session_state.get('skipped_stages', 'N/A')}")
            st.success("🔄 已恢复之前的会话状态")

    except Exception as e:
        logger.error(f"Failed to restore session state: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")


def auto_save_session_state():
    """Automatically save session state periodically"""
    current_time = time.time()
    last_save = getattr(st.session_state, 'last_state_save', 0)

    # Save state every 30 seconds if processing or has progress
    if (current_time - last_save > 30 and
        (st.session_state.processing or st.session_state.progress > 0)):
        save_session_state()
        st.session_state.last_state_save = current_time



def check_and_display_recovery_options():
    """Check for interrupted tasks and display recovery options"""
    # Use a container to isolate the recovery options
    recovery_container = st.empty()

    # Only show recovery options if we have an interrupted task
    should_show_recovery = (
        st.session_state.processing and
        hasattr(st.session_state, 'stage_start_time') and
        st.session_state.stage_start_time and
        (time.time() - st.session_state.stage_start_time) > 300  # More than 5 minutes
    )

    if should_show_recovery:
        with recovery_container.container():
            st.warning("⚠️ 检测到可能中断的任务处理")
            elapsed = time.time() - st.session_state.stage_start_time
            st.info(f"任务已运行 {int(elapsed/60)} 分钟，可能由于连接断开而中断")

            col1, col2 = st.columns(2)
            with col1:
                # Use a distinct widget key to avoid conflicts with query params
                if st.button("🔄 重新开始当前阶段", key="restart_stage_btn", type="primary"):                    # Trigger restart by setting a flag that will be handled after rendering
                    st.query_params["restart_stage"] = "true"
                    st.rerun()

            with col2:
                if st.button("⏭️ 跳过当前阶段", key="skip_interrupted"):
                    # Trigger skip by setting a flag that will be handled after rendering
                    st.query_params["skip_stage"] = "true"
                    st.rerun()

            st.markdown("---")
    else:
        # Clear the recovery container if no recovery needed
        recovery_container.empty()


if __name__ == "__main__":
    main()
