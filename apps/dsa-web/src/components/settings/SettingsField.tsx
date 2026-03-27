import { useState } from 'react';
import type React from 'react';
import { EyeToggleIcon, Select } from '../common';
import type { ConfigValidationIssue, SystemConfigItem } from '../../types/systemConfig';
import { getFieldDescriptionZh, getFieldExampleZh, getFieldTitleZh } from '../../utils/systemConfigI18n';

function isMultiValueField(item: SystemConfigItem): boolean {
  const validation = (item.schema?.validation ?? {}) as Record<string, unknown>;
  return Boolean(validation.multiValue ?? validation.multi_value);
}

function parseMultiValues(value: string): string[] {
  if (!value) {
    return [''];
  }

  const values = value
    .split(/[\n,]+/)
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
  return values.length ? values : [''];
}

function serializeMultiValues(values: string[]): string {
  return values.map((entry) => entry.trim()).join(',');
}

interface SettingsFieldProps {
  item: SystemConfigItem;
  value: string;
  disabled?: boolean;
  onChange: (key: string, value: string) => void;
  issues?: ConfigValidationIssue[];
}

function renderFieldControl(
  item: SystemConfigItem,
  value: string,
  disabled: boolean,
  onChange: (nextValue: string) => void,
  isSecretVisible: boolean,
  onToggleSecretVisible: () => void,
  isPasswordEditable: boolean,
  onPasswordFocus: () => void,
) {
  const schema = item.schema;
  const commonClass = 'input-terminal';
  const controlType = schema?.uiControl ?? 'text';
  const isMultiValue = isMultiValueField(item);

  if (controlType === 'textarea') {
    return (
      <textarea
        className={`${commonClass} min-h-[92px] resize-y`}
        value={value}
        disabled={disabled || !schema?.isEditable}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }

  if (isMultiValue && controlType !== 'password') {
    const values = parseMultiValues(value);

    return (
      <div className="space-y-2">
        {values.map((entry, index) => (
          <div className="flex items-center gap-2" key={`${item.key}-${index}`}>
            <input
              type={controlType === 'number' ? 'number' : 'text'}
              className={`${commonClass} flex-1`}
              value={entry}
              disabled={disabled || !schema?.isEditable}
              onChange={(event) => {
                const nextValues = [...values];
                nextValues[index] = event.target.value;
                onChange(serializeMultiValues(nextValues));
              }}
            />
            <button
              type="button"
              className="btn-secondary !px-3 !py-2 text-xs"
              disabled={disabled || !schema?.isEditable || values.length <= 1}
              onClick={() => {
                const nextValues = values.filter((_, rowIndex) => rowIndex !== index);
                onChange(serializeMultiValues(nextValues.length ? nextValues : ['']));
              }}
            >
              删除
            </button>
          </div>
        ))}

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary !px-3 !py-2 text-xs"
            disabled={disabled || !schema?.isEditable}
            onClick={() => onChange(serializeMultiValues([...values, '']))}
          >
            添加一项
          </button>
        </div>
      </div>
    );
  }

  if (controlType === 'select' && schema?.options?.length) {
    return (
      <Select
        value={value}
        onChange={onChange}
        options={schema.options.map((option) => ({ value: option, label: option }))}
        disabled={disabled || !schema.isEditable}
        placeholder="请选择"
      />
    );
  }

  if (controlType === 'switch') {
    const checked = value.trim().toLowerCase() === 'true';
    return (
      <label className="inline-flex cursor-pointer items-center gap-3">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled || !schema?.isEditable}
          onChange={(event) => onChange(event.target.checked ? 'true' : 'false')}
        />
        <span className="text-sm text-secondary">{checked ? '已启用' : '未启用'}</span>
      </label>
    );
  }

  if (controlType === 'password') {
    if (isMultiValue) {
      const values = parseMultiValues(value);

      return (
        <div className="space-y-2">
          {values.map((entry, index) => (
            <div className="flex items-center gap-2" key={`${item.key}-${index}`}>
              <input
                type={isSecretVisible ? 'text' : 'password'}
                readOnly={!isPasswordEditable}
                onFocus={onPasswordFocus}
                className={`${commonClass} flex-1`}
                value={entry}
                disabled={disabled || !schema?.isEditable}
                onChange={(event) => {
                  const nextValues = [...values];
                  nextValues[index] = event.target.value;
                  onChange(serializeMultiValues(nextValues));
                }}
              />
              <button
                type="button"
                className="btn-secondary !p-2"
                disabled={disabled || !schema?.isEditable}
                onClick={onToggleSecretVisible}
                title={isSecretVisible ? '隐藏' : '显示'}
                aria-label={isSecretVisible ? '隐藏密码' : '显示密码'}
              >
                <EyeToggleIcon visible={isSecretVisible} />
              </button>
              <button
                type="button"
                className="btn-secondary !px-3 !py-2 text-xs"
                disabled={disabled || !schema?.isEditable || values.length <= 1}
                onClick={() => {
                  const nextValues = values.filter((_, rowIndex) => rowIndex !== index);
                  onChange(serializeMultiValues(nextValues.length ? nextValues : ['']));
                }}
              >
                删除
              </button>
            </div>
          ))}

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-secondary !px-3 !py-2 text-xs"
              disabled={disabled || !schema?.isEditable}
              onClick={() => onChange(serializeMultiValues([...values, '']))}
            >
              添加 Key
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="flex items-center gap-2">
        <input
          type={isSecretVisible ? 'text' : 'password'}
          readOnly={!isPasswordEditable}
          onFocus={onPasswordFocus}
          className={`${commonClass} flex-1`}
          value={value}
          disabled={disabled || !schema?.isEditable}
          onChange={(event) => onChange(event.target.value)}
        />
        <button
          type="button"
          className="btn-secondary !p-2"
          disabled={disabled || !schema?.isEditable}
          onClick={onToggleSecretVisible}
          title={isSecretVisible ? '隐藏' : '显示'}
          aria-label={isSecretVisible ? '隐藏密码' : '显示密码'}
        >
          <EyeToggleIcon visible={isSecretVisible} />
        </button>
      </div>
    );
  }

  const inputType = controlType === 'number' ? 'number' : controlType === 'time' ? 'time' : 'text';

  return (
    <input
      type={inputType}
      className={commonClass}
      value={value}
      disabled={disabled || !schema?.isEditable}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export const SettingsField: React.FC<SettingsFieldProps> = ({
  item,
  value,
  disabled = false,
  onChange,
  issues = [],
}) => {
  const schema = item.schema;
  const isMultiValue = isMultiValueField(item);
  const title = getFieldTitleZh(item.key, item.key);
  const description = getFieldDescriptionZh(item.key);
  const example = getFieldExampleZh(item.key);
  const hasError = issues.some((issue) => issue.severity === 'error');
  const [isSecretVisible, setIsSecretVisible] = useState(false);
  const [isPasswordEditable, setIsPasswordEditable] = useState(false);
  const [copyButtonText, setCopyButtonText] = useState('复制示例');

  const canApplyExample = Boolean(example) && schema?.isEditable && !disabled && value !== example;

  const handleCopyExample = async () => {
    if (!example) {
      return;
    }

    try {
      await navigator.clipboard.writeText(example);
      setCopyButtonText('已复制');
      window.setTimeout(() => setCopyButtonText('复制示例'), 1800);
    } catch (error) {
      console.error('Failed to copy config example:', error);
      setCopyButtonText('复制失败');
      window.setTimeout(() => setCopyButtonText('复制示例'), 1800);
    }
  };

  return (
    <div className={`rounded-xl border p-4 ${hasError ? 'border-red-500/35' : 'border-white/8'} bg-elevated/50`}>
      <div className="mb-2 flex items-center gap-2">
        <label className="text-sm font-semibold text-white" htmlFor={`setting-${item.key}`}>
          {title}
        </label>
        {schema?.isSensitive ? (
          <span className="badge badge-purple text-[10px]">敏感</span>
        ) : null}
      </div>

      {description ? (
        <p className="mb-3 text-xs text-muted" title={description}>
          {description}
        </p>
      ) : null}

      {example ? (
        <div className="mb-3 rounded-lg border border-amber-300/20 bg-amber-300/5 px-3 py-3 text-[11px] text-amber-100">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="shrink-0 uppercase tracking-wide text-amber-200/80">示例</span>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn-secondary !px-2.5 !py-1 text-[11px]"
                onClick={() => onChange(item.key, example)}
                disabled={!canApplyExample}
              >
                填入示例
              </button>
              <button
                type="button"
                className="btn-secondary !px-2.5 !py-1 text-[11px]"
                onClick={() => void handleCopyExample()}
              >
                {copyButtonText}
              </button>
            </div>
          </div>
          <code className="mt-2 block overflow-x-auto whitespace-nowrap text-amber-50">{example}</code>
        </div>
      ) : null}

      <div id={`setting-${item.key}`}>
        {renderFieldControl(
          item,
          value,
          disabled,
          (nextValue) => onChange(item.key, nextValue),
          isSecretVisible,
          () => setIsSecretVisible((previous) => !previous),
          isPasswordEditable,
          () => setIsPasswordEditable(true),
        )}
      </div>

      {schema?.isSensitive ? (
        <p className="mt-2 text-[11px] text-secondary">
          密钥默认隐藏，可点击眼睛图标查看明文。
          {isMultiValue ? ' 支持添加多个输入框进行增删。' : ''}
        </p>
      ) : null}

      {isMultiValue && !schema?.isSensitive ? (
        <p className="mt-2 text-[11px] text-secondary">
          多值字段支持逐项编辑，保存时会自动整理为逗号分隔格式。
        </p>
      ) : null}

      {issues.length ? (
        <div className="mt-2 space-y-1">
          {issues.map((issue, index) => (
            <p
              key={`${issue.code}-${issue.key}-${index}`}
              className={issue.severity === 'error' ? 'text-xs text-danger' : 'text-xs text-warning'}
            >
              {issue.message}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
};
