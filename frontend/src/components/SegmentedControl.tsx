interface Option<T extends string> {
  value: T
  label: string
}

interface SegmentedControlProps<T extends string> {
  label: string
  value: T
  options: Option<T>[]
  onChange: (value: T) => void
}

/** A small radio group styled as buttons (keyboard: Tab to the group, arrows to move). */
export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <fieldset className="inline-flex rounded-md bg-slate-200/70 p-0.5">
      <legend className="sr-only">{label}</legend>
      {options.map((option) => (
        <label
          key={option.value}
          className={`cursor-pointer rounded px-3 py-1 text-sm font-medium has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-cyan-600 ${
            value === option.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'
          }`}
        >
          <input
            type="radio"
            name={label}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
            className="sr-only"
          />
          {option.label}
        </label>
      ))}
    </fieldset>
  )
}
