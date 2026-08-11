function ResultsToolbar({ count, selectedCount, allSelected, onSelectAll, onClear, children }) {
  return (
    <div className="results-toolbar">
      <div className="results-title"><span className="section-kicker">Results</span><h2>{count} Hotels Found</h2></div>
      <div className="selection-tools">
        <label><input type="checkbox" checked={allSelected} onChange={(event) => onSelectAll(event.target.checked)} /> Select All</label>
        <span>{selectedCount} selected</span>
        <button type="button" disabled={!selectedCount} onClick={onClear}>Clear</button>
      </div>
      <div className="result-actions">{children}</div>
    </div>
  )
}

export default ResultsToolbar
