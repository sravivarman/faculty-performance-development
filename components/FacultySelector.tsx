"use client";

import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import { Person } from "@/lib/api";

type Props = {
  value: number | null;
  onChange: (value: number | null) => void;
  faculty?: Person[];
  label?: string;
  placeholder?: string;
  clearable?: boolean;
  disabled?: boolean;
  loading?: boolean;
  error?: string;
  includeInactive?: boolean;
};

function display(person: Person) {
  return person.name + (person.employee_id ? " · " + person.employee_id : "") + (person.is_active ? "" : " (historical)");
}

export default function FacultySelector({
  value,
  onChange,
  faculty,
  label = "Faculty",
  placeholder = "Search Faculty name or employee ID",
  clearable = true,
  disabled = false,
  loading = false,
  error,
  includeInactive = true,
}: Props) {
  const inputId = useId();
  const listId = useId();
  const root = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const selected = faculty?.find((person) => person.id === value);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const matches = useMemo(() => (faculty || []).filter((person) => {
    if (!includeInactive && !person.is_active && person.id !== value) return false;
    const candidate = (person.name + " " + (person.employee_id || "")).toLocaleLowerCase();
    return !normalizedQuery || candidate.includes(normalizedQuery);
  }), [faculty, includeInactive, normalizedQuery, value]);

  useEffect(() => {
    setActiveIndex(0);
  }, [normalizedQuery, open]);
  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  function choose(person: Person) {
    onChange(person.id);
    setQuery("");
    setOpen(false);
  }
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => open ? Math.min(index + 1, Math.max(matches.length - 1, 0)) : 0);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => open ? Math.max(index - 1, 0) : Math.max(matches.length - 1, 0));
    } else if (event.key === "Enter" && open && matches[activeIndex]) {
      event.preventDefault();
      choose(matches[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  const visibleValue = open ? query : selected ? display(selected) : query;

  function openSearch() {
    if (!open) setQuery("");
    setOpen(true);
  }

  return (
    <div className="faculty-selector" ref={root}>
      <label htmlFor={inputId}>{label}</label>
      <div className={"faculty-selector-control" + (clearable && value !== null ? " has-clear" : "")}>
        <input
          id={inputId}
          type="search"
          role="combobox"
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={open && matches[activeIndex] ? listId + "-" + matches[activeIndex].id : undefined}
          placeholder={placeholder}
          value={visibleValue}
          disabled={disabled}
          onFocus={openSearch}
          onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
          onKeyDown={onKeyDown}
        />
        {clearable && value !== null && (
          <button type="button" className="secondary small faculty-selector-clear" onMouseDown={(event) => event.preventDefault()} onClick={() => { onChange(null); setQuery(""); setOpen(false); }} aria-label={"Clear " + label}>
            Clear
          </button>
        )}
      </div>
      <span className="sr-only" aria-live="polite">{selected ? "Selected: " + display(selected) : "No Faculty selected"}</span>
      {error && <div className="error" role="alert">{error}</div>}
      {open && (
        <ul id={listId} role="listbox" aria-label={label + " matches"} className="faculty-selector-options">
          {loading ? <li role="status">Loading Faculty Master…</li> : !faculty ? <li role="status">Faculty Master is unavailable.</li> : !matches.length ? (
            <li role="status">No Faculty records match the search.</li>
          ) : matches.map((person, index) => (
            <li
              id={listId + "-" + person.id}
              key={person.id}
              role="option"
              aria-selected={person.id === value}
              className={index === activeIndex ? "active" : ""}
              onMouseDown={(event) => event.preventDefault()}
            >
              <button type="button" className="faculty-selector-option" onClick={() => choose(person)}>
                {display(person)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
