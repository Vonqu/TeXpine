def format_stage_label(stage_key, spine_type=None):
    """Return canonical stage label used in CSV and event logs.

    Rules:
    - For new stage identifiers: 'pelvis_rotation'->阶段1, 'spine_curvature_single'->阶段2, etc.
    - For int stages: use '阶段{n}', except S-type where 2->2A and 3->2B
    - For legacy str keys: '2a'->阶段2A, '2b'->阶段2B, '3a'/'3b'->阶段3
    - Fallback: prefix with '阶段'
    """
    try:
        # 新的标志符映射
        stage_identifier_map = {
            'pelvis_rotation': '阶段1',
            'spine_curvature_single': '阶段2',
            'spine_curvature_upper': '阶段2A',
            'spine_curvature_lower': '阶段2B',
            'pelvis_tilt': '阶段3',
            'shoulder_tilt': '阶段4'
        }
        
        # 如果是新的标志符，直接返回映射结果
        if str(stage_key) in stage_identifier_map:
            return stage_identifier_map[str(stage_key)]
        
        # Numeric stage with optional spine type context
        if isinstance(stage_key, int):
            if str(spine_type).upper() == 'S':
                if stage_key == 2:
                    return '阶段2A'
                if stage_key == 3:
                    return '阶段2B'
            return f'阶段{stage_key}'

        key_str = str(stage_key).strip()
        # direct numeric in string
        if key_str in {'1', '2', '3', '4'}:
            return f'阶段{key_str}'
        lower = key_str.lower()
        if lower == '2a':
            return '阶段2A'
        if lower == '2b':
            return '阶段2B'
        # if lower in {'3a', '3b'}:
        #     return '阶段3'
        return f'阶段{key_str}'
    except Exception:
        return f'阶段{stage_key}'


def canonical_stage_labels():
    """List of canonical stage labels used across the project."""
    return ['阶段1', '阶段2', '阶段2A', '阶段2B', '阶段3', '阶段4'] 