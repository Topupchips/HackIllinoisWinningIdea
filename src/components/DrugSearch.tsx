import { useState, useEffect, useRef } from 'react';
import { Search } from 'lucide-react';
import { searchDrugs, getCompoundByName, type CompoundResponse } from '../services/api';
import './DrugSearch.css';

interface DrugSearchProps {
  onSelect: (compound: CompoundResponse) => void;
  onClose?: () => void;
  draggable?: boolean;
}

export default function DrugSearch({ onSelect, onClose, draggable = true }: DrugSearchProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      setError(null);
      const { results } = await searchDrugs(query);
      setSuggestions(results);
      setLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const handleSelect = async (name: string) => {
    setFetching(true);
    setError(null);
    const compound = await getCompoundByName(name);
    setFetching(false);
    if (compound?.smiles) {
      onSelect(compound);
      setQuery('');
      setSuggestions([]);
      onClose?.();
    } else {
      setError(`Could not find "${name}" in PubChem`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose?.();
  };

  return (
    <div className="drug-search">
      <div className="drug-search-input-wrap">
        <Search size={18} className="search-icon" />
        <input
          ref={inputRef}
          type="text"
          placeholder="Search drug by name (e.g. aspirin, ibuprofen)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          className="drug-search-input"
        />
      </div>
      {loading && <p className="drug-search-status">Searching...</p>}
      {error && <p className="drug-search-error">{error}</p>}
      {fetching && <p className="drug-search-status">Fetching compound data...</p>}
      {suggestions.length > 0 && (
        <ul className="drug-search-suggestions">
          {suggestions.map((s) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => handleSelect(s)}
                draggable={draggable}
                onDragStart={(e) => {
                  e.dataTransfer.setData('drug_name', s);
                  e.dataTransfer.effectAllowed = 'copy';
                }}
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
