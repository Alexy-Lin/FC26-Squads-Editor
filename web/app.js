const app = {
  state: null,
  meta: null,
  selectedPlayer: null,
  selectedTeam: null,
  playerTimer: null,
  teamTimer: null,
  playerRequestId: 0,
  transferRequestId: 0,
  transferSelection: { from: null, to: null },
  transferTeams: { from: null, to: null },
  exactTransferTimer: null,
  exactTransferTarget: null,
  exactTransferTargetTeam: null,
  transferSort: {
    from: { key: "jerseynumber", direction: "asc" },
    to: { key: "jerseynumber", direction: "asc" },
  },
  teamSort: { key: "jerseynumber", direction: "asc" },
};

const MIN_TRANSFER_ROSTER_SIZE = 16;
const MAX_TRANSFER_ROSTER_SIZE = 42;

// 国家队选拔默认男足，可用“男足/女足”按钮切换
let nationalGender = 0;

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (options.method && options.method !== "GET") headers["X-Editor-Token"] = app.state.token;
  const response = await fetch(path, { ...options, headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast show${error ? " error" : ""}`;
  clearTimeout(element.timer);
  element.timer = setTimeout(() => element.className = "toast", 3200);
}

function debounce(key, fn, delay = 220) {
  clearTimeout(app[key]);
  app[key] = setTimeout(fn, delay);
}

function switchView(viewName) {
  $$(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.view === viewName));
  $$(".view").forEach(view => view.classList.toggle("active", view.id === `${viewName}View`));
  if (viewName === "national" && nationalDraft.team && !nationalDraft.dirty) {
    loadNational(nationalDraft.team.teamid);
  }
  if (viewName === "quick") loadQuickPanel();
}

async function refreshState() {
  const previousToken = app.state?.token;
  app.state = await api("/api/state");
  if (!app.state.token) app.state.token = previousToken;
  $("#savePath").textContent = app.state.save_path || "尚未加载存档";
  $("#playerCount").textContent = `${app.state.player_count.toLocaleString()} 名`;
  const pending = $("#pendingBadge");
  pending.textContent = `${app.state.pending_changes} 项待保存`;
  pending.classList.toggle("changed", app.state.pending_changes > 0);
  $("#saveButton").disabled = app.state.pending_changes === 0;
  $("#resetButton").disabled = app.state.pending_changes === 0;
}

function fillMeta() {
  const position = $("#positionFilter");
  app.meta.positions.forEach(item => position.add(new Option(item.label, item.value)));
  fillTransferTeams();
  fillNationalTeams();
  const nationalPosition = $("#nationalPosition");
  nationalPosition.replaceChildren(new Option("全部位置", ""));
  app.meta.positions.forEach(item => nationalPosition.add(new Option(item.label, item.label)));
}

function nationalTeamsOfGender(gender) {
  return (app.meta?.national_teams || []).filter(team => (team.gender ?? 0) === gender);
}

function updateGenderToggle() {
  $$("#nationalGenderToggle .gender-option").forEach(button => {
    button.classList.toggle("active", Number(button.dataset.gender) === nationalGender);
  });
}

function fillNationalTeams() {
  const select = $("#nationalTeam");
  if (!select) return;
  const previous = select.value;
  const teams = nationalTeamsOfGender(nationalGender);
  select.replaceChildren(new Option(nationalGender === 1 ? "请选择女足国家队" : "请选择国家队", ""));
  teams.forEach(team => select.add(new Option(team.label, team.teamid)));
  if (previous && teams.some(team => String(team.teamid) === previous)) {
    select.value = previous;
  } else if (previous) {
    select.value = "";
  }
  updateGenderToggle();
}

function setNationalGender(gender) {
  if (gender === nationalGender) return;
  if (nationalDraft.dirty && !confirm("切换男足/女足会放弃当前选拔草稿，继续吗？")) {
    updateGenderToggle();
    return;
  }
  nationalGender = gender;
  clearNational();
  fillNationalTeams();
}

function fillTransferTeams() {
  ["from", "to"].forEach(side => {
    const input = transferPickerInput(side);
    input.value = "";
    input.dataset.teamId = "";
  });
  app.transferSelection = { from: null, to: null };
}

function transferPickerInput(side) {
  return $(`#transfer${side === "from" ? "From" : "To"}Team`);
}

function transferPickerOptions(side) {
  return $(`#transfer${side === "from" ? "From" : "To"}Options`);
}

function normalizeTeamSearch(value) {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase().trim();
}

function teamSearchText(team) {
  return normalizeTeamSearch([
    team.teamid,
    team.name_en,
    team.name_cn,
    team.label,
  ].filter(value => value !== null && value !== undefined).join(" "));
}

function teamSearchMatches(searchable, query) {
  const needle = normalizeTeamSearch(query);
  return !needle || normalizeTeamSearch(searchable).includes(needle);
}

function teamMatchesSearch(team, query) {
  return teamSearchMatches(teamSearchText(team), query);
}

function transferTeamCandidates(query) {
  const nationalIds = new Set((app.meta.national_teams || []).map(item => Number(item.teamid)));
  const teams = (app.meta.clubs || []).filter(item => !nationalIds.has(Number(item.teamid)));
  return teams.filter(item => teamMatchesSearch(item, query));
}

function renderTransferSuggestions(side) {
  const input = transferPickerInput(side);
  const root = transferPickerOptions(side);
  const teams = transferTeamCandidates(input.value);
  root.hidden = false;
  root.innerHTML = teams.length ? teams.map(team => `
    <button class="transfer-team-option" type="button" role="option" data-transfer-side="${side}" data-transfer-team-id="${team.teamid}">
      <span class="transfer-team-option-name">${escapeHtml(team.label)}</span>
      <span class="transfer-team-option-id">ID ${team.teamid}</span>
    </button>`).join("") : `<div class="transfer-team-no-match">没有匹配的俱乐部或自由球员</div>`;
}

function closeTransferSuggestions() {
  ["from", "to"].forEach(side => { transferPickerOptions(side).hidden = true; });
}

function clearTransferPicker(side, showSuggestions = false) {
  const input = transferPickerInput(side);
  input.value = "";
  input.dataset.teamId = "";
  app.transferSelection[side] = null;
  clearTransferTeams("请选择来源和目标球队");
  if (showSuggestions) renderTransferSuggestions(side);
}

function selectTransferTeam(side, teamId) {
  const team = (app.meta.clubs || []).find(item => Number(item.teamid) === Number(teamId));
  if (!team) return;
  const input = transferPickerInput(side);
  input.value = team.label;
  input.dataset.teamId = String(team.teamid);
  app.transferSelection[side] = Number(team.teamid);
  transferPickerOptions(side).hidden = true;
  loadTransferRosters();
}

function transferTeamTitle(team) {
  const name = team.name_cn || team.name_en || team.name || `球队 ${team.teamid}`;
  return `${name} (ID=${team.teamid})`;
}

function isFreeAgentTeam(team) {
  return Number(team?.teamid) === 111592;
}

function transferCount(team) {
  return (team.roster || []).length;
}

function transferCountText(team) {
  const count = transferCount(team);
  if (isFreeAgentTeam(team)) return `${count} 人 · 不限人数`;
  const suffix = count < MIN_TRANSFER_ROSTER_SIZE
    ? " · 低于下限"
    : count > MAX_TRANSFER_ROSTER_SIZE ? " · 超过上限" : "";
  return `${count} 人${suffix}`;
}

function transferSortButton(side, key, label) {
  const sort = app.transferSort[side];
  const active = sort.key === key;
  const indicator = active ? (sort.direction === "asc" ? "↑" : "↓") : "↕";
  const ariaSort = active ? (sort.direction === "asc" ? "ascending" : "descending") : "none";
  return `<button type="button" class="sort-button${active ? " active" : ""}" data-transfer-sort-side="${side}" data-transfer-sort-key="${key}" aria-sort="${ariaSort}">${label}<span class="sort-indicator" aria-hidden="true">${indicator}</span></button>`;
}

function transferJerseyCell(player, freeAgent) {
  if (freeAgent) return `<span class="transfer-no-jersey" title="自由球员不使用球衣号码">—</span>`;
  return `<span class="transfer-jersey-value">${escapeHtml(player.jerseynumber || "—")}</span>`;
}

function renderTransferColumn(root, team, targetTeam, side) {
  const freeAgent = isFreeAgentTeam(team);
  const players = sortedRoster(team.roster || [], app.transferSort[side]);
  const sourceBlocked = !freeAgent && transferCount(team) <= MIN_TRANSFER_ROSTER_SIZE;
  const targetBlocked = !isFreeAgentTeam(targetTeam) && transferCount(targetTeam) >= MAX_TRANSFER_ROSTER_SIZE;
  const disabled = sourceBlocked || targetBlocked;
  const reason = sourceBlocked
    ? `来源球队转出后不能少于 ${MIN_TRANSFER_ROSTER_SIZE} 人`
    : targetBlocked ? `目标球队转入后不能超过 ${MAX_TRANSFER_ROSTER_SIZE} 人` : "";
  const direction = side === "from" ? "转入右侧 →" : "← 转入左侧";
  const rows = players.map(player => `
    <tr>
      <td>${transferJerseyCell(player, freeAgent)}</td>
      <td><button type="button" class="player-id-link" data-open-player-id="${player.playerid}" title="打开 ${escapeHtml(player.name)} 的球员编辑页">${player.playerid}</button></td>
      <td><strong>${escapeHtml(player.name || `球员 ${player.playerid}`)}</strong>${player.name_cn ? `<small>${escapeHtml(player.name_cn)}</small>` : ""}</td>
      <td><strong>${player.overallrating ?? "-"}</strong></td>
      <td>${escapeHtml(player.primary_position || "-")}</td>
      <td><button class="button primary transfer-action" type="button" ${disabled ? "disabled" : ""}${reason ? ` title="${escapeHtml(reason)}"` : ""} data-transfer-player-id="${player.playerid}" data-transfer-from-team="${team.teamid}" data-transfer-to-team="${targetTeam.teamid}">${disabled ? "不可转入" : direction}</button></td>
    </tr>`).join("");
  root.innerHTML = `
    ${freeAgent ? `<div class="free-agent-banner"><strong>自由球员池</strong><span>不限人数 · 不使用球衣号码</span></div>` : ""}
    <div class="transfer-table-wrap">
      <table class="roster-table transfer-table">
        <thead><tr><th>${freeAgent ? "号码" : transferSortButton(side, "jerseynumber", "号码")}</th><th>球员 ID</th><th>球员</th><th>${transferSortButton(side, "overallrating", "能力")}</th><th>${transferSortButton(side, "primary_position", "位置")}</th><th>转会</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="6"><div class="transfer-empty">${freeAgent ? "自由球员池为空" : "这支球队暂无球员"}</div></td></tr>`}</tbody>
      </table>
    </div>`;
}

function renderTransferTeams(fromTeam, toTeam) {
  app.transferTeams = { from: fromTeam, to: toTeam };
  $("#transferFromTitle").textContent = transferTeamTitle(fromTeam);
  $("#transferToTitle").textContent = transferTeamTitle(toTeam);
  $("#transferFromCount").textContent = transferCountText(fromTeam);
  $("#transferToCount").textContent = transferCountText(toTeam);
  $("#transferFromCount").classList.toggle("transfer-count-warning", !isFreeAgentTeam(fromTeam) && (transferCount(fromTeam) < MIN_TRANSFER_ROSTER_SIZE || transferCount(fromTeam) > MAX_TRANSFER_ROSTER_SIZE));
  $("#transferToCount").classList.toggle("transfer-count-warning", !isFreeAgentTeam(toTeam) && (transferCount(toTeam) < MIN_TRANSFER_ROSTER_SIZE || transferCount(toTeam) > MAX_TRANSFER_ROSTER_SIZE));
  renderTransferColumn($("#transferFromRoster"), fromTeam, toTeam, "from");
  renderTransferColumn($("#transferToRoster"), toTeam, fromTeam, "to");
}

function clearTransferTeams(message = "请选择两支不同的球队") {
  app.transferRequestId += 1;
  app.transferTeams = { from: null, to: null };
  $("#transferFromTitle").textContent = "来源球队";
  $("#transferToTitle").textContent = "目标球队";
  $("#transferFromCount").textContent = "0 人";
  $("#transferToCount").textContent = "0 人";
  $("#transferFromCount").classList.remove("transfer-count-warning");
  $("#transferToCount").classList.remove("transfer-count-warning");
  $("#transferFromRoster").innerHTML = `<div class="transfer-empty">${escapeHtml(message)}</div>`;
  $("#transferToRoster").innerHTML = `<div class="transfer-empty">${escapeHtml(message)}</div>`;
}

async function loadTransferRosters() {
  const fromTeamId = app.transferSelection.from;
  const toTeamId = app.transferSelection.to;
  const requestId = ++app.transferRequestId;
  if (!fromTeamId || !toTeamId) {
    clearTransferTeams("请选择来源和目标球队");
    return;
  }
  if (fromTeamId === toTeamId) {
    clearTransferTeams("来源球队和目标球队不能相同");
    return;
  }
  try {
    const [fromTeam, toTeam] = await Promise.all([
      api(`/api/teams/${fromTeamId}`),
      api(`/api/teams/${toTeamId}`),
    ]);
    if (requestId === app.transferRequestId) renderTransferTeams(fromTeam, toTeam);
  } catch (error) { toast(error.message, true); }
}

function bindTransferPicker(side) {
  const input = transferPickerInput(side);
  const options = transferPickerOptions(side);
  input.addEventListener("click", () => clearTransferPicker(side, true));
  input.addEventListener("focus", () => renderTransferSuggestions(side));
  input.addEventListener("input", () => {
    input.dataset.teamId = "";
    app.transferSelection[side] = null;
    clearTransferTeams("请选择来源和目标球队");
    renderTransferSuggestions(side);
  });
  input.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      options.hidden = true;
      return;
    }
    if (event.key !== "Enter") return;
    const first = $("[data-transfer-team-id]", options);
    if (!first) return;
    event.preventDefault();
    selectTransferTeam(side, Number(first.dataset.transferTeamId));
  });
  options.addEventListener("click", event => {
    const option = event.target.closest?.("[data-transfer-team-id]");
    if (option) selectTransferTeam(side, Number(option.dataset.transferTeamId));
  });
}

async function transferPlayer(playerId, fromTeamId, toTeamId, button) {
  button.disabled = true;
  try {
    const result = await api("/api/transfers", {
      method: "POST",
      body: JSON.stringify({ player_id: playerId, from_team_id: fromTeamId, to_team_id: toTeamId }),
    });
    const jersey = result.jerseynumber ? `，号码 ${result.jerseynumber}` : "";
    toast(`${result.player_name} 已转入目标球队${jersey}`);
    await refreshState();
    await loadTransferRosters();
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
  }
}

function handleTransferClick(event) {
  const sortButton = event.target.closest?.("[data-transfer-sort-key]");
  if (sortButton) {
    const side = sortButton.dataset.transferSortSide;
    const sort = app.transferSort[side];
    const key = sortButton.dataset.transferSortKey;
    const root = side === "from" ? $("#transferFromRoster") : $("#transferToRoster");
    app.transferSort[side] = sort.key === key
      ? { key, direction: sort.direction === "asc" ? "desc" : "asc" }
      : { key, direction: "asc" };
    renderTransferColumn(root, app.transferTeams[side], app.transferTeams[side === "from" ? "to" : "from"], side);
    return;
  }
  const playerLink = event.target.closest?.("[data-open-player-id]");
  if (playerLink) {
    openPlayerFromRoster(Number(playerLink.dataset.openPlayerId));
    return;
  }
  const button = event.target.closest?.("[data-transfer-player-id]");
  if (!button) return;
  transferPlayer(
    Number(button.dataset.transferPlayerId),
    Number(button.dataset.transferFromTeam),
    Number(button.dataset.transferToTeam),
    button,
  );
}

function exactTransferTargetLabel(team) {
  if (!team) return "全体球员";
  const name = team.name_cn || team.name_en || team.name || `球队 ${team.teamid}`;
  return `全体球员 → ${name}`;
}

async function loadExactTransferTarget(teamId) {
  app.exactTransferTarget = Number(teamId);
  try {
    app.exactTransferTargetTeam = await api(`/api/teams/${teamId}`);
    $("#exactTransferTitle").textContent = exactTransferTargetLabel(app.exactTransferTargetTeam);
    await searchExactTransferPlayers();
  } catch (error) { toast(error.message, true); }
}

async function searchExactTransferPlayers() {
  if (!app.exactTransferTarget || !app.exactTransferTargetTeam) {
    $("#exactTransferCount").textContent = "0 条结果";
    $("#exactTransferResults").innerHTML = `<div class="transfer-empty">请先从左侧选择目标球队</div>`;
    return;
  }
  const params = new URLSearchParams({
    q: $("#exactPlayerSearch").value,
    nation: $("#exactNationFilter").value,
    min_overall: $("#exactOverallFilter").value,
    limit: "300",
  });
  try {
    const players = await api(`/api/players?${params}`);
    renderExactTransferResults(players);
  } catch (error) { toast(error.message, true); }
}

function renderExactTransferResults(players) {
  const root = $("#exactTransferResults");
  const target = app.exactTransferTargetTeam;
  const targetFull = !isFreeAgentTeam(target) && transferCount(target) >= MAX_TRANSFER_ROSTER_SIZE;
  $("#exactTransferCount").textContent = `${players.length} 条结果`;
  if (!players.length) {
    root.innerHTML = `<div class="transfer-empty">没有符合筛选条件的球员</div>`;
    return;
  }
  const rows = players.map(player => {
    const sameTeam = Number(player.club_id) === Number(target.teamid);
    const noSource = !player.club_id;
    const disabled = targetFull || sameTeam || noSource;
    const reason = targetFull
      ? `目标球队不能超过 ${MAX_TRANSFER_ROSTER_SIZE} 人`
      : sameTeam ? "球员已在目标球队" : noSource ? "球员没有可用的俱乐部关系记录" : "";
    const action = targetFull ? "目标已满" : sameTeam ? "已在队中" : noSource ? "不可转入" : "转入球队 →";
    return `<tr>
      <td><button type="button" class="player-id-link" data-open-player-id="${player.playerid}">${player.playerid}</button></td>
      <td class="exact-player-name"><strong>${escapeHtml(player.name)}</strong><small>${escapeHtml(player.name_cn || "")}</small></td>
      <td>${escapeHtml(player.nation || "-")}</td>
      <td><strong>${player.overallrating ?? "-"}</strong></td>
      <td>${escapeHtml(player.position || "-")}</td>
      <td>${escapeHtml(player.club || "自由球员")}</td>
      <td><button class="button primary transfer-action" type="button" ${disabled ? "disabled" : ""}${reason ? ` title="${escapeHtml(reason)}"` : ""} data-exact-transfer-player-id="${player.playerid}" data-exact-transfer-from-team="${player.club_id ?? ""}">${action}</button></td>
    </tr>`;
  }).join("");
  root.innerHTML = `<table class="roster-table exact-player-table">
    <thead><tr><th>球员 ID</th><th>球员</th><th>国籍</th><th>能力</th><th>位置</th><th>当前俱乐部</th><th>操作</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

async function transferExactPlayer(playerId, fromTeamId, button) {
  const targetTeamId = app.exactTransferTarget;
  if (!targetTeamId) return toast("请先选择目标球队", true);
  button.disabled = true;
  try {
    const result = await api("/api/transfers", {
      method: "POST",
      body: JSON.stringify({ player_id: playerId, from_team_id: fromTeamId, to_team_id: targetTeamId }),
    });
    const jersey = result.jerseynumber ? `，号码 ${result.jerseynumber}` : "";
    toast(`${result.player_name} 已转入目标球队${jersey}`);
    await refreshState();
    await loadExactTransferTarget(targetTeamId);
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
  }
}

function handleExactTransferClick(event) {
  const playerLink = event.target.closest?.("[data-open-player-id]");
  if (playerLink) {
    openPlayerFromRoster(Number(playerLink.dataset.openPlayerId));
    return;
  }
  const button = event.target.closest?.("[data-exact-transfer-player-id]");
  if (!button) return;
  transferExactPlayer(
    Number(button.dataset.exactTransferPlayerId),
    Number(button.dataset.exactTransferFromTeam),
    button,
  );
}

function clearExactTransferTarget() {
  app.exactTransferTarget = null;
  app.exactTransferTargetTeam = null;
  $("#exactTransferTitle").textContent = "全体球员";
  $("#exactTransferCount").textContent = "0 条结果";
  $("#exactTransferResults").innerHTML = `<div class="transfer-empty">请先从左侧选择目标球队</div>`;
}

function bindExactTransferPage() {
  const targetInput = $("#exactTransferTarget");
  bindPlayerEditorInput(targetInput);
  const options = targetInput.closest(".field").querySelector(".field-options");
  options.addEventListener("mousedown", event => {
    const option = event.target.closest?.("[data-team-option-id]");
    if (option) loadExactTransferTarget(Number(option.dataset.teamOptionId));
  });
  targetInput.addEventListener("click", () => {
    if (!targetInput.dataset.teamId) clearExactTransferTarget();
  });
  targetInput.addEventListener("input", clearExactTransferTarget);
  targetInput.addEventListener("keydown", event => {
    if (event.key === "Enter" && targetInput.dataset.teamId) {
      loadExactTransferTarget(Number(targetInput.dataset.teamId));
    }
  });
  ["#exactPlayerSearch", "#exactNationFilter", "#exactOverallFilter"].forEach(selector => {
    $(selector).addEventListener("input", () => debounce("exactTransferTimer", searchExactTransferPlayers));
  });
  $("#exactTransferResults").addEventListener("click", handleExactTransferClick);
}

async function searchPlayers() {
  const params = new URLSearchParams({
    q: $("#playerSearch").value,
    nation: $("#nationFilter").value,
    position: $("#positionFilter").value,
    min_overall: $("#overallFilter").value,
    limit: "150",
  });
  try {
    const players = await api(`/api/players?${params}`);
    renderPlayerResults(players);
  } catch (error) { toast(error.message, true); }
}

function renderPlayerResults(players) {
  const root = $("#playerResults");
  if (!players.length) {
    root.innerHTML = `<div class="result-item"><span class="result-meta">没有匹配的球员</span></div>`;
    return;
  }
  root.innerHTML = players.map(player => `
    <button class="result-item ${player.playerid === app.selectedPlayer ? "active" : ""}" data-player-id="${player.playerid}">
      <span class="result-main"><span>${escapeHtml(player.name)}</span><span>${player.overallrating}</span></span>
      <span class="result-cn">${escapeHtml(player.name_cn || player.nation)}</span>
      <span class="result-meta">ID ${player.playerid} · ${escapeHtml(player.position)} · ${escapeHtml(player.club || "自由球员")}</span>
    </button>`).join("");
  $$('[data-player-id]', root).forEach(button => button.addEventListener("click", () => loadPlayer(Number(button.dataset.playerId), true)));
}

function focusSelectedPlayer() {
  const button = $$('[data-player-id]', $("#playerResults")).find(item => Number(item.dataset.playerId) === app.selectedPlayer);
  if (!button) return;
  button.focus({ preventScroll: true });
  button.scrollIntoView({ block: "nearest" });
}

function movePlayerSelection(direction) {
  const buttons = $$('[data-player-id]', $("#playerResults"));
  if (!buttons.length) return;
  const currentIndex = buttons.findIndex(button => Number(button.dataset.playerId) === app.selectedPlayer);
  const startIndex = currentIndex < 0 ? (direction > 0 ? 0 : buttons.length - 1) : currentIndex;
  const nextIndex = Math.max(0, Math.min(buttons.length - 1, startIndex + direction));
  if (nextIndex === currentIndex) return;
  loadPlayer(Number(buttons[nextIndex].dataset.playerId), true);
}

function handlePlayerResultsKeydown(event) {
  const button = event.target.closest?.('[data-player-id]');
  if (!button || !$("#playerResults").contains(button)) return;
  if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
  event.preventDefault();
  movePlayerSelection(event.key === "ArrowUp" ? -1 : 1);
}

async function loadPlayer(playerId, keepListFocus = false) {
  const requestId = ++app.playerRequestId;
  const listHasFocus = keepListFocus || $("#playerResults").contains(document.activeElement);
  try {
    app.selectedPlayer = playerId;
    const player = await api(`/api/players/${playerId}`);
    if (requestId !== app.playerRequestId) return;
    renderPlayer(player);
    await searchPlayers();
    if (listHasFocus && requestId === app.playerRequestId) focusSelectedPlayer();
  } catch (error) { toast(error.message, true); }
}

async function openPlayerFromRoster(playerId) {
  switchView("players");
  $("#playerSearch").value = String(playerId);
  $("#nationFilter").value = "";
  $("#overallFilter").value = "";
  $("#positionFilter").value = "";
  await loadPlayer(playerId);
  $("#playerDetail").scrollTop = 0;
}

function renderPlayer(player) {
  const overall = findField(player, "overallrating");
  const potential = findField(player, "potential");
  const position = findField(player, "preferredposition1");
  const positionText = position?.options.find(item => item.value === position.value)?.label || position?.value || "-";
  const head = player.head
    ? `<img class="player-head" src="${player.head}" alt="${escapeHtml(player.name)}">`
    : `<div class="player-head head-fallback">${escapeHtml((player.name_cn || player.name).slice(0, 1))}</div>`;
  const groups = player.fields.map(group => `
    <section class="attribute-group">
      <h3>${escapeHtml(group.name)}</h3>
      <div class="attribute-fields">${group.fields.map(renderField).join("")}</div>
    </section>`).join("");
  const root = $("#playerDetail");
  root.className = "detail panel";
  root.innerHTML = `
    <div class="player-hero">
      ${head}
      <div class="player-title">
        <h2>${escapeHtml(player.name)}</h2>
        <div class="cn">${escapeHtml(player.name_cn || player.common_name || "")}</div>
        <div class="sub">球员 ID ${player.playerid}${player.common_name ? ` · 通用名 ${escapeHtml(player.common_name)}` : ""}</div>
      </div>
      <div class="hero-stats">
        <div class="stat"><strong>${overall?.value ?? "-"}</strong><span>总评</span></div>
        <div class="stat"><strong>${potential?.value ?? "-"}</strong><span>潜力</span></div>
        <div class="stat"><strong>${escapeHtml(positionText)}</strong><span>位置</span></div>
      </div>
    </div>
    <section class="team-affiliation">
      <h3>所属球队</h3>
      <div class="team-grid">
        <div class="field field-with-options"><span>国家队</span><input id="nationalTeamInput" data-editable-input data-team-option-kind="national" data-team-id="${player.national_team.teamid ?? ""}" data-team-original-id="${player.national_team.teamid ?? ""}" value="${escapeHtml(player.national_team.label)}" data-original="${escapeHtml(player.national_team.label)}" placeholder="输入国家队名称或 ID" autocomplete="off" spellcheck="false"><div class="field-options" role="listbox" hidden></div></div>
        <div class="field field-with-options"><span>俱乐部 / 自由球员</span><input id="clubInput" data-editable-input data-team-option-kind="club" data-team-id="${player.club.teamid ?? ""}" data-team-original-id="${player.club.teamid ?? ""}" value="${escapeHtml(player.club.label)}" data-original="${escapeHtml(player.club.label)}" placeholder="输入俱乐部或自由球员" autocomplete="off" spellcheck="false"><div class="field-options" role="listbox" hidden></div></div>
      </div>
    </section>
    <div class="attribute-grid">${groups}</div>
    ${renderTraits(player)}
    <div class="sticky-actions">
      <button class="button ghost" id="reloadPlayerButton">重置表单</button>
      <button class="button primary" id="applyPlayerButton">应用球员修改</button>
    </div>`;
  bindPlayerEditorInputs(root);
  $$('[data-trait-bit]', root).forEach(input => input.addEventListener("change", () => updateTrait(player.playerid, input)));
  $("#reloadPlayerButton").addEventListener("click", () => loadPlayer(player.playerid));
  $("#applyPlayerButton").addEventListener("click", () => applyPlayer(player.playerid));
}

function findField(player, name) {
  for (const group of player.fields) {
    const field = group.fields.find(item => item.name === name);
    if (field) return field;
  }
  return null;
}

function renderField(field) {
  const attrs = `data-field="${field.name}" data-original="${escapeHtml(field.value)}"${field.read_only ? "" : " data-editable-input"}`;
  let control;
  if (field.options.length) {
    const selected = field.options.find(item => String(item.value) === String(field.value));
    const selectedLabel = selected?.label ?? field.value;
    const options = field.options.map(item => `
      <button class="field-option" type="button" role="option" data-field-option-value="${escapeHtml(item.value)}" data-field-option-label="${escapeHtml(item.label)}">
        <span>${escapeHtml(item.label)}</span><small>${escapeHtml(item.value)}</small>
      </button>`).join("");
    control = `<input type="search" ${attrs} value="${escapeHtml(selectedLabel)}" data-option-field data-option-value="${escapeHtml(field.value)}" data-option-label="${escapeHtml(selectedLabel)}" data-option-original-label="${escapeHtml(selectedLabel)}" autocomplete="off" spellcheck="false" placeholder="输入字符匹配或选择"><div class="field-options" role="listbox" hidden>${options}<div class="field-options-no-match" hidden>没有匹配的选项</div></div>`;
  } else if (field.type === "Integer" || field.type === "Float") {
    const step = field.type === "Float" ? "0.01" : "1";
    control = `<input type="number" ${attrs} value="${escapeHtml(field.value)}" min="${field.min}" max="${field.max}" step="${step}" ${field.read_only ? "readonly" : ""}>`;
  } else {
    control = `<input type="text" ${attrs} value="${escapeHtml(field.value)}" ${field.read_only ? "readonly" : ""}>`;
  }
  return `<div class="field${field.options.length ? " field-with-options" : ""}"><span>${escapeHtml(field.label)}</span>${control}</div>`;
}

function renderTraits(player) {
  const groups = player.traits || {};
  const items = [...(groups.regular || []), ...(groups.regular2 || []), ...(groups.icon || []), ...(groups.icon2 || [])];
  if (!items.length) return "";
  return `<section class="attribute-group trait-group"><h3>特性 / 图标特性</h3><div class="trait-fields">${items.map(item => `
    <label class="trait-toggle"><input type="checkbox" data-trait-bit data-trait-bank="${item.bank}" data-trait-bit-value="${item.bit}" data-trait-icon="${item.icon ? "1" : "0"}" ${item.enabled ? "checked" : ""}><span>${escapeHtml(item.name)}</span><small>bit ${item.bit}</small></label>`).join("")}</div></section>`;
}

async function updateTrait(playerId, input) {
  const checked = input.checked;
  try {
    const result = await api(`/api/players/${playerId}/traits`, {
      method: "POST",
      body: JSON.stringify({
        bank: Number(input.dataset.traitBank),
        bit: Number(input.dataset.traitBitValue),
        enabled: checked,
        icon: input.dataset.traitIcon === "1",
      }),
    });
    toast(`特性已${checked ? "启用" : "关闭"}，保存后写入新存档`);
    await refreshState();
  } catch (error) {
    input.checked = !checked;
    toast(error.message, true);
  }
}

function hideFieldOptions(input) {
  const options = input.closest(".field")?.querySelector(".field-options");
  if (options) options.hidden = true;
}

function renderTeamInputOptions(input, options) {
  const items = input.dataset.teamOptionKind === "club" ? app.meta.clubs : app.meta.national_teams;
  options.innerHTML = `${items.map(item => `
    <button class="field-option" type="button" role="option" data-team-option-id="${item.teamid}" data-team-option-label="${escapeHtml(item.label)}" data-team-option-search="${escapeHtml(teamSearchText(item))}">
      <span>${escapeHtml(item.label)}</span><small>${item.teamid}</small>
    </button>`).join("")}<div class="field-options-no-match" hidden>没有匹配的球队</div>`;
}

function filterPlayerInputOptions(input) {
  const options = input.closest(".field")?.querySelector(".field-options");
  if (!options) return;
  if (input.hasAttribute("data-team-option-kind") && !options.dataset.rendered) {
    renderTeamInputOptions(input, options);
    options.dataset.rendered = "1";
  }
  const query = input.hasAttribute("data-team-option-kind")
    ? normalizeTeamSearch(input.value)
    : input.value.trim().toLocaleLowerCase();
  let visible = 0;
  $$('[data-field-option-value], [data-team-option-id]', options).forEach(option => {
    const searchable = option.dataset.fieldOptionValue
      ? `${option.dataset.fieldOptionValue} ${option.dataset.fieldOptionLabel}`
      : option.dataset.teamOptionSearch || option.textContent;
    const matches = input.hasAttribute("data-team-option-kind")
      ? teamSearchMatches(searchable, query)
      : !query || String(searchable ?? "").toLocaleLowerCase().includes(query);
    option.hidden = !matches;
    if (matches) visible += 1;
  });
  const noMatch = $(".field-options-no-match", options);
  noMatch.hidden = visible > 0;
  options.hidden = false;
}

function selectFieldOption(input, option) {
  input.value = option.dataset.fieldOptionLabel;
  input.dataset.optionValue = option.dataset.fieldOptionValue;
  input.dataset.optionLabel = option.dataset.fieldOptionLabel;
  delete input.dataset.editingStarted;
  hideFieldOptions(input);
  input.focus();
}

function selectTeamInputOption(input, option) {
  input.value = option.dataset.teamOptionLabel;
  input.dataset.teamId = option.dataset.teamOptionId;
  input.dataset.teamOptionLabel = option.dataset.teamOptionLabel;
  delete input.dataset.editingStarted;
  hideFieldOptions(input);
  input.focus();
}

function playerFieldValue(input) {
  if (!input.hasAttribute("data-option-field")) return input.value;
  if (input.dataset.optionValue !== undefined && input.value === input.dataset.optionLabel) return input.dataset.optionValue;
  const query = input.value.trim().toLocaleLowerCase();
  const option = $$('[data-field-option-value]', input.closest(".field") || document).find(item => (
    item.dataset.fieldOptionLabel.toLocaleLowerCase() === query
    || item.dataset.fieldOptionValue.toLocaleLowerCase() === query
  ));
  return option ? option.dataset.fieldOptionValue : input.value;
}

function restorePlayerInput(input) {
  if (input.value.trim()) return;
  if (input.hasAttribute("data-option-field")) {
    const originalLabel = input.dataset.optionOriginalLabel ?? input.dataset.optionLabel ?? input.dataset.original ?? "";
    input.value = originalLabel;
    input.dataset.optionValue = input.dataset.original;
    input.dataset.optionLabel = originalLabel;
    return;
  }
  if (input.hasAttribute("data-team-option-kind")) {
    input.value = input.dataset.original ?? "";
    input.dataset.teamId = input.dataset.teamOriginalId ?? "";
    return;
  }
  input.value = input.dataset.original ?? "";
}

function bindPlayerEditorInput(input) {
  if (input.readOnly || input.disabled) return;
  const hasOptions = input.hasAttribute("data-option-field");
  const hasTeamOptions = input.hasAttribute("data-team-option-kind");
  const hasQuickOptions = hasOptions || hasTeamOptions;
  const label = input.closest(".field")?.querySelector(":scope > span");
  label?.addEventListener("click", () => input.click());
  input.addEventListener("click", () => {
    if (!input.dataset.editingStarted) {
      input.value = "";
      if (hasQuickOptions) {
        delete input.dataset.optionValue;
        delete input.dataset.optionLabel;
        delete input.dataset.teamId;
      }
      input.dataset.editingStarted = "1";
    }
    input.focus();
    if (hasQuickOptions) filterPlayerInputOptions(input);
  });
  input.addEventListener("focus", () => {
    if (hasQuickOptions) filterPlayerInputOptions(input);
  });
  input.addEventListener("input", () => {
    if (hasQuickOptions) {
      delete input.dataset.optionValue;
      delete input.dataset.optionLabel;
      delete input.dataset.teamId;
      filterPlayerInputOptions(input);
    }
  });
  input.addEventListener("blur", () => {
    delete input.dataset.editingStarted;
    restorePlayerInput(input);
    setTimeout(() => {
      if (!input.closest(".field")?.contains(document.activeElement)) hideFieldOptions(input);
    }, 120);
  });
  if (hasQuickOptions) {
    const options = input.closest(".field").querySelector(".field-options");
    options.addEventListener("mousedown", event => {
      const option = event.target.closest?.("[data-field-option-value], [data-team-option-id]");
      if (!option) return;
      event.preventDefault();
      if (hasOptions) selectFieldOption(input, option);
      else selectTeamInputOption(input, option);
    });
    input.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        hideFieldOptions(input);
        return;
      }
      if (event.key !== "Enter") return;
      const option = $$('[data-field-option-value]:not([hidden]), [data-team-option-id]:not([hidden])', options)[0];
      if (!option) return;
      event.preventDefault();
      if (hasOptions) selectFieldOption(input, option);
      else selectTeamInputOption(input, option);
    });
  }
}

function bindPlayerEditorInputs(root) {
  $$('[data-editable-input]', root).forEach(bindPlayerEditorInput);
}

function resolveTeamValue(input, items) {
  const value = input.value.trim();
  const match = items.find(item => item.label === value);
  return match ? match.teamid : value;
}

function resolvePlayerTeamValue(input, items) {
  return input.dataset.teamId || resolveTeamValue(input, items);
}

async function applyPlayer(playerId) {
  const body = { fields: {} };
  $$('[data-field]', $("#playerDetail")).forEach(input => {
    if (input.disabled || input.readOnly) return;
    const value = playerFieldValue(input);
    if (String(value) !== String(input.dataset.original)) body.fields[input.dataset.field] = value;
  });
  const club = $("#clubInput");
  const national = $("#nationalTeamInput");
  if (club.value !== club.dataset.original) body.club = resolvePlayerTeamValue(club, app.meta.clubs);
  if (national.value !== national.dataset.original) body.national_team = resolvePlayerTeamValue(national, app.meta.national_teams);
  if (!Object.keys(body.fields).length && !("club" in body) && !("national_team" in body)) {
    toast("没有字段发生变化");
    return;
  }
  try {
    const result = await api(`/api/players/${playerId}`, { method: "POST", body: JSON.stringify(body) });
    toast(`已应用 ${result.applied} 项修改，保存后写入新存档`);
    await refreshState();
    await loadPlayer(playerId);
  } catch (error) { toast(error.message, true); }
}

async function searchTeams() {
  try {
    const teams = await api(`/api/teams?q=${encodeURIComponent($("#teamSearch").value)}`);
    $("#teamCount").textContent = `${teams.length} 支`;
    renderTeamResults(teams);
  } catch (error) { toast(error.message, true); }
}

function renderTeamResults(teams) {
  const root = $("#teamResults");
  root.innerHTML = teams.map(team => `
    <button class="result-item ${team.teamid === app.selectedTeam ? "active" : ""}" data-team-id="${team.teamid}">
      <span class="result-main"><span>${escapeHtml(team.name)}</span><span>${team.overallrating ?? "-"}</span></span>
      <span class="result-meta">ID ${team.teamid} · 攻 ${team.attackrating ?? "-"} · 中 ${team.midfieldrating ?? "-"} · 防 ${team.defenserating ?? "-"}</span>
    </button>`).join("");
  $$('[data-team-id]', root).forEach(button => button.addEventListener("click", () => loadTeam(Number(button.dataset.teamId))));
}

async function loadTeam(teamId) {
  try {
    app.selectedTeam = teamId;
    const team = await api(`/api/teams/${teamId}`);
    renderTeam(team);
    searchTeams();
  } catch (error) { toast(error.message, true); }
}

const POSITION_SORT_ORDER = ["GK", "SW", "RWB", "RB", "CB", "LB", "LWB", "CDM", "RM", "CM", "LM", "CAM", "CF", "RW", "ST", "LW"];

function collectRosterDraft(root) {
  const draft = {};
  $$(".jersey-input", root).forEach(input => {
    draft[input.dataset.playerId] = { value: input.value, original: input.dataset.original };
  });
  return draft;
}

function rosterSortValue(player, key) {
  const raw = player[key];
  if (raw === null || raw === undefined || raw === "") return null;
  if (key === "primary_position") {
    const index = POSITION_SORT_ORDER.indexOf(String(raw));
    return index < 0 ? null : index;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function compareRosterValues(left, right, direction) {
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  return (left - right) * direction;
}

function sortedRoster(roster, sort = app.teamSort) {
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...roster].sort((left, right) => {
    const result = compareRosterValues(
      rosterSortValue(left, sort.key),
      rosterSortValue(right, sort.key),
      direction,
    );
    return result || left.playerid - right.playerid;
  });
}

function sortTeamRoster(team, root, key) {
  if (app.teamSort.key === key) {
    app.teamSort.direction = app.teamSort.direction === "asc" ? "desc" : "asc";
  } else {
    app.teamSort = { key, direction: "asc" };
  }
  renderTeam(team, collectRosterDraft(root));
}

function sortButton(key, label) {
  const active = app.teamSort.key === key;
  const direction = app.teamSort.direction;
  const indicator = active ? (direction === "asc" ? "↑" : "↓") : "↕";
  const ariaSort = active ? (direction === "asc" ? "ascending" : "descending") : "none";
  return `<button type="button" class="sort-button${active ? " active" : ""}" data-sort-key="${key}" aria-sort="${ariaSort}">${label}<span class="sort-indicator" aria-hidden="true">${indicator}</span></button>`;
}

function rosterRows(roster, draft = {}) {
  return sortedRoster(roster).map(player => {
    const current = draft[player.playerid]?.value ?? player.jerseynumber ?? "";
    const original = draft[player.playerid]?.original ?? player.jerseynumber ?? "";
    return `<tr><td><input class="jersey-input" type="number" min="1" max="99" value="${escapeHtml(current)}" data-player-id="${player.playerid}" data-original="${escapeHtml(original)}"></td><td><button type="button" class="player-id-link" data-open-player-id="${player.playerid}" title="打开 ${escapeHtml(player.name)} 的球员编辑页">${player.playerid}</button></td><td>${escapeHtml(player.name)}</td><td>${escapeHtml(player.name_cn)}</td><td><strong>${player.overallrating ?? "-"}</strong></td><td>${escapeHtml(player.primary_position || "-")}</td></tr>`;
  }).join("");
}

function renderTeam(team, draft = {}) {
  const root = $("#teamDetail");
  root.className = "detail panel";
  root.innerHTML = `
    <div class="team-hero">
      <div><span class="eyebrow">TEAM ID ${team.teamid}</span><h2>${escapeHtml(team.name_cn || team.name_en || team.name)}</h2>${team.name_cn && team.name_en ? `<div class="result-meta">${escapeHtml(team.name_en)}</div>` : ""}</div>
      <div class="rating-row">
        <div class="stat"><strong>${team.overallrating ?? "-"}</strong><span>总评</span></div>
        <div class="stat"><strong>${team.attackrating ?? "-"}</strong><span>进攻</span></div>
        <div class="stat"><strong>${team.midfieldrating ?? "-"}</strong><span>中场</span></div>
        <div class="stat"><strong>${team.defenserating ?? "-"}</strong><span>防守</span></div>
      </div>
    </div>
    <table class="roster-table">
      <thead><tr><th>${sortButton("jerseynumber", "号码")}</th><th>球员 ID</th><th>英文名</th><th>中文名</th><th>${sortButton("overallrating", "能力值")}</th><th>${sortButton("primary_position", "主要位置")}</th></tr></thead>
      <tbody>${rosterRows(team.roster, draft)}</tbody>
    </table>
    <div class="sticky-actions"><button class="button ghost" id="reloadTeamButton">重置号码</button><button class="button primary" id="applyNumbersButton">应用号码修改</button></div>`;
  $("#reloadTeamButton").addEventListener("click", () => loadTeam(team.teamid));
  $("#applyNumbersButton").addEventListener("click", () => applyNumbers(team.teamid, root));
  $$('[data-sort-key]', root).forEach(button => button.addEventListener("click", () => sortTeamRoster(team, root, button.dataset.sortKey)));
  $$('[data-open-player-id]', root).forEach(button => button.addEventListener("click", () => openPlayerFromRoster(Number(button.dataset.openPlayerId))));
}

async function applyNumbers(teamId, root = $("#teamDetail")) {
  const assignments = {};
  $$(".jersey-input", root).forEach(input => {
    if (input.value !== input.dataset.original) assignments[input.dataset.playerId] = Number(input.value);
  });
  if (!Object.keys(assignments).length) return toast("没有号码发生变化");
  try {
    const result = await api(`/api/teams/${teamId}/numbers`, { method: "POST", body: JSON.stringify({ assignments }) });
    toast(`已应用 ${result.applied} 个号码修改`);
    await refreshState();
    await loadTeam(teamId);
  } catch (error) { toast(error.message, true); }
}

async function loadQuickPanel() {
  await Promise.all([loadQuickLegends(), loadQuickBirthdates(), loadQuickPeak()]);
}

async function loadQuickLegends() {
  const summary = $("#legendSummary");
  const preview = $("#legendPreview");
  const button = $("#quickAddLegends");
  if (!summary || !preview || !button) return;
  try {
    const data = await api("/api/quick/legends");
    const skipped = data.women_skipped_count
      ? `（已排除 ${data.women_skipped_count} 名女足传奇）`
      : "";
    summary.textContent = data.missing_count
      ? `当前有 ${data.missing_count} 名男足传奇不在存档（共识别 ${data.available_count} 名）${skipped}。`
      : `当前存档已经包含全部男足传奇球员${skipped}。`;
    const names = (data.missing || []).slice(0, 16).map(item => item.name);
    preview.textContent = names.length
      ? `${names.join("、")}${data.missing_count > names.length ? " 等" : ""}`
      : "无需添加。";
    button.disabled = !data.missing_count;
  } catch (error) {
    summary.textContent = error.message;
    preview.textContent = "传奇数据库不可用。";
    button.disabled = true;
  }
}

async function applyQuickAge18() {
  const button = $("#quickAge18");
  const status = $("#quickAge18Status");
  button.disabled = true;
  status.textContent = "正在处理当前存档中的球员…";
  try {
    const result = await api("/api/quick/age18", { method: "POST", body: "{}" });
    status.textContent = result.players_updated
      ? `已暂存 ${result.players_updated.toLocaleString()} 名球员的年龄修改。`
      : "所有球员已经是 18 岁，无需修改。";
    await refreshState();
    await loadQuickBirthdates();
    toast(result.players_updated
      ? `已将 ${result.players_updated.toLocaleString()} 名球员设置为 18 岁，请保存为新存档`
      : "所有球员已经是 18 岁");
  } catch (error) {
    status.textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function addQuickLegends() {
  const button = $("#quickAddLegends");
  button.disabled = true;
  try {
    const result = await api("/api/quick/add-legends", { method: "POST", body: "{}" });
    toast(result.added
      ? `已暂存 ${result.added} 名男足传奇球员，请保存为新存档`
      : (result.women_skipped
        ? `没有需要添加的男足传奇（已排除 ${result.women_skipped} 名女足）`
        : "没有需要添加的传奇球员"));
    await refreshState();
    await Promise.all([loadQuickPanel(), searchPlayers(), loadTransferRosters()]);
  } catch (error) {
    toast(error.message, true);
    await loadQuickPanel();
  }
}

async function loadQuickBirthdates() {
  const summary = $("#birthdateSummary");
  const button = $("#quickRestoreBirthdays");
  if (!summary || !button) return;
  try {
    const data = await api("/api/quick/birthdates");
    if (data.available) {
      summary.textContent = data.restore_count
        ? `快照里有 ${data.saved_players.toLocaleString()} 名球员，其中 ${data.restore_count.toLocaleString()} 人可以被还原。`
        : "所有球员的生日都已经和快照一致。";
      button.disabled = !data.restore_count;
    } else {
      summary.textContent = data.message || "还没有生日快照。";
      button.disabled = true;
    }
    if (data.invalid_count) {
      summary.textContent += ` 另有 ${data.invalid_count} 名球员生日越界（游戏会隐藏他们）。`;
    }
  } catch (error) {
    summary.textContent = error.message;
    button.disabled = true;
  }
}

async function restoreQuickBirthdays() {
  const button = $("#quickRestoreBirthdays");
  const status = $("#birthdateStatus");
  button.disabled = true;
  status.textContent = "正在还原原始生日…";
  try {
    const result = await api("/api/quick/restore-birthdays", { method: "POST", body: "{}" });
    status.textContent = result.players_updated
      ? `已暂存 ${result.players_updated.toLocaleString()} 名球员的生日还原。`
      : "所有球员的生日已经是原始值。";
    await refreshState();
    await loadQuickBirthdates();
    toast(result.players_updated
      ? `已还原 ${result.players_updated.toLocaleString()} 名球员的原始生日，请保存为新存档`
      : "生日已经是原始值");
  } catch (error) {
    status.textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function renderListDialog({ eyebrow, title, summary, columns, rows }) {
  const dialog = $("#listDialog");
  if (!dialog) return;
  $("#listDialogEyebrow").textContent = eyebrow;
  $("#listDialogTitle").textContent = title;
  $("#listDialogSummary").textContent = summary;
  $("#listDialogHead").innerHTML = columns
    .map(column => `<th${column.align === "right" ? ' class="list-num"' : ""}>${escapeHtml(column.label)}</th>`)
    .join("");
  $("#listDialogBody").innerHTML = rows.length
    ? rows.map(cells => `<tr>${cells.join("")}</tr>`).join("")
    : `<tr><td class="list-empty" colspan="${columns.length}">没有记录</td></tr>`;
  if (!dialog.open) dialog.showModal();
}

function openListDialogLoading(eyebrow, title) {
  renderListDialog({ eyebrow, title, summary: "正在读取名单…", columns: [{ label: "名单" }], rows: [] });
}

async function openLegendList() {
  openListDialogLoading("LEGEND PLAYERS", "传奇球员名单（男足）");
  try {
    const data = await api("/api/quick/legends?scope=all");
    if (!Array.isArray(data.available)) {
      throw new Error("后端没有返回完整名单：编辑器改了代码后需要重启一次（关闭窗口重新运行 start_editor.bat）。");
    }
    const rows = (data.available || []).map(item => [
      `<td class="list-id">${item.playerid}</td>`,
      `<td><strong>${escapeHtml(item.name)}</strong></td>`,
      `<td>${item.missing
        ? '<span class="list-tag add">将添加</span>'
        : '<span class="list-tag own">已有</span>'}</td>`,
      `<td class="list-num">${item.overallrating}</td>`,
      `<td>${escapeHtml(item.birthdate_source)}</td>`,
      `<td>${item.birthdate_fixed ? "真实生日" : "源数据生日"}</td>`,
      `<td>${item.origin === "extra" ? "额外补充" : "官方清单"}</td>`,
    ]);
    renderListDialog({
      eyebrow: "LEGEND PLAYERS",
      title: "传奇球员名单（男足）",
      summary: `共识别 ${data.available_count} 名男足传奇：当前存档已有 ${data.present_count} 名，待添加 ${data.missing_count} 名；`
        + `另有 ${data.women_skipped_count} 名女足 ICON/英雄按设置跳过。`,
      columns: [
        { label: "ID" }, { label: "姓名" }, { label: "状态" }, { label: "OVR", align: "right" },
        { label: "生日" }, { label: "生日来源" }, { label: "清单来源" },
      ],
      rows,
    });
  } catch (error) {
    renderListDialog({
      eyebrow: "LEGEND PLAYERS",
      title: "传奇球员名单（男足）",
      summary: error.message,
      columns: [{ label: "名单" }],
      rows: [],
    });
  }
}

async function openPeakList() {
  openListDialogLoading("VETERAN PEAK", "现役老将名单（FIFA19 巅峰）");
  try {
    const data = await api("/api/quick/peak?include_done=1");
    if (typeof data.roster_count !== "number" || !data.roster_count) {
      throw new Error("后端没有返回完整名单：编辑器改了代码后需要重启一次（关闭窗口重新运行 start_editor.bat）。");
    }
    const rows = (data.candidates || []).map(item => [
      `<td class="list-id">${item.playerid}</td>`,
      `<td><strong>${escapeHtml(item.name)}</strong></td>`,
      `<td class="list-num">${item.age}</td>`,
      `<td class="list-num">${item.overallrating}</td>`,
      `<td class="list-num">${item.peak}</td>`,
      `<td class="list-num">${item.gain ? `+${item.gain}` : "—"}</td>`,
      `<td class="list-num">${item.raiseable}</td>`,
      `<td>${item.done
        ? '<span class="list-tag done">已达标</span>'
        : '<span class="list-tag todo">待恢复</span>'}</td>`,
      `<td>${item.gk ? "门将" : "外场"}</td>`,
      `<td>${escapeHtml(item.club || "无俱乐部")}</td>`,
    ]);
    const done = data.roster_count - data.count;
    renderListDialog({
      eyebrow: "VETERAN PEAK",
      title: "现役老将名单（FIFA19 巅峰）",
      summary: `共 ${data.roster_count} 名（年龄 ≥ ${data.min_age}、FIFA19 巅峰 OVR ≥ ${data.min_peak}）：`
        + `待恢复 ${data.count} 名，已达标 ${done} 名；门将 ${data.gk_count} 名，无俱乐部 ${data.clubless_count} 名。`,
      columns: [
        { label: "ID" }, { label: "姓名" }, { label: "年龄", align: "right" },
        { label: "现在", align: "right" }, { label: "巅峰", align: "right" },
        { label: "OVR提升", align: "right" }, { label: "需补项数", align: "right" },
        { label: "状态" }, { label: "位置" }, { label: "俱乐部" },
      ],
      rows,
    });
  } catch (error) {
    renderListDialog({
      eyebrow: "VETERAN PEAK",
      title: "现役老将名单（FIFA19 巅峰）",
      summary: error.message,
      columns: [{ label: "名单" }],
      rows: [],
    });
  }
}

async function loadQuickPeak() {
  const summary = $("#peakSummary");
  const preview = $("#peakPreview");
  const button = $("#quickPeakRestore");
  if (!summary || !preview || !button) return;
  try {
    const data = await api("/api/quick/peak");
    if (data.count) {
      const extra = [];
      if (data.gk_count) extra.push(`${data.gk_count} 名门将`);
      if (data.clubless_count) extra.push(`${data.clubless_count} 人无俱乐部`);
      if (data.ovr_unchanged_count) extra.push(`${data.ovr_unchanged_count} 人只需补齐单项属性`);
      summary.textContent = `可恢复 ${data.count} 名现役老将`
        + (extra.length ? `（含 ${extra.join("、")}）` : "") + "。";
    } else {
      summary.textContent = "当前存档里的现役老将都已经在 FIFA19 巅峰。";
    }
    const names = (data.candidates || []).slice(0, 12)
      .map(item => `${item.name} ${item.overallrating}${item.gain ? `→${item.peak}` : "(峰值)"}·${item.raiseable}项`);
    preview.textContent = names.length
      ? `${names.join("、")}${data.count > names.length ? " 等" : ""}`
      : "无需恢复。";
    button.disabled = !data.count;
  } catch (error) {
    summary.textContent = error.message;
    preview.textContent = "缺少 FIFA19 巅峰数据。";
    button.disabled = true;
  }
}

async function restoreQuickPeak() {
  const button = $("#quickPeakRestore");
  const status = $("#peakStatus");
  button.disabled = true;
  status.textContent = "正在恢复现役老将的巅峰数据…";
  try {
    const result = await api("/api/quick/peak", { method: "POST", body: JSON.stringify({ only_raise: true }) });
    status.textContent = result.restored_count
      ? `已暂存 ${result.restored_count} 名球员 / ${result.field_count.toLocaleString()} 项属性。`
      : "没有需要恢复的球员。";
    await refreshState();
    await Promise.all([loadQuickPeak(), searchPlayers()]);
    toast(result.restored_count
      ? `已恢复 ${result.restored_count} 名现役老将的巅峰数据，请保存为新存档`
      : "没有需要恢复的球员");
  } catch (error) {
    status.textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function saveChanges() {
  if (nationalDraft.busy) return toast("国家队操作处理中，请稍后再保存");
  if (nationalDraft.dirty) return toast("请先应用国家队选拔草稿，或重置草稿后再保存", true);
  try {
    const result = await api("/api/save", { method: "POST", body: "{}" });
    toast(`已生成并验证 ${result.name}`);
    app.selectedPlayer = null;
    app.selectedTeam = null;
    await refreshState();
    await searchPlayers();
    await searchTeams();
    await Promise.all([loadTransferRosters(), loadQuickPanel()]);
  } catch (error) { toast(error.message, true); }
}

async function resetChanges() {
  if (nationalDraft.busy) return toast("国家队操作处理中，请稍后再重置");
  if (!confirm("确定放弃尚未保存的全部修改吗？")) return;
  try {
    await api("/api/reset", { method: "POST", body: "{}" });
    clearNational();
    toast("已放弃全部未保存修改");
    await refreshState();
    if (app.selectedPlayer) await loadPlayer(app.selectedPlayer);
    if (app.selectedTeam) await loadTeam(app.selectedTeam);
    await Promise.all([loadTransferRosters(), loadQuickPanel()]);
  } catch (error) { toast(error.message, true); }
}

async function applySaveAndRefresh(saveName) {
  clearNational();
  $("#openDialog").close();
  app.selectedPlayer = null;
  app.selectedTeam = null;
  app.meta = await api("/api/meta");
  fillMeta();
  await refreshState();
  await searchPlayers();
  await searchTeams();
  await Promise.all([loadTransferRosters(), loadQuickPanel()]);
  toast(saveName ? `已加载 ${saveName}` : "存档已加载");
}

async function loadSaveFromPath(path) {
  const state = await api("/api/open", { method: "POST", body: JSON.stringify({ path }) });
  await applySaveAndRefresh(state.save_name);
}

function openSaveDialog(message) {
  const hint = $("#openDialogHint");
  if (hint) {
    hint.textContent = message
      ? `${message}；可用下面的备用方式打开存档。`
      : "正常情况下点击顶部“打开存档”会直接弹出系统文件选择窗口。这里是备用方式。";
  }
  const fileInput = $("#openFileInput");
  if (fileInput) fileInput.value = "";
  const pathInput = $("#openPathInput");
  if (pathInput) pathInput.value = app.state?.save_path || "";
  $("#openDialog").showModal();
}

async function openSaveViaPicker() {
  if (nationalDraft.busy) return toast("国家队操作处理中，请稍后再打开存档");
  if (nationalDraft.dirty && !confirm("打开存档将放弃国家队选拔草稿，继续吗？")) return;
  const button = $("#openButton");
  if (button) button.disabled = true;
  try {
    const picked = await api("/api/pick-save", { method: "POST", body: "{}" });
    if (picked.cancelled) return;
    if (picked.error || !picked.path) {
      openSaveDialog(picked.error || "没有拿到所选存档路径");
      return;
    }
    await loadSaveFromPath(picked.path);
  } catch (error) {
    openSaveDialog(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}

async function openSave(event) {
  event.preventDefault();
  if (nationalDraft.busy) return toast("国家队操作处理中，请稍后再打开存档");
  const file = $("#openFileInput")?.files?.[0];
  const path = ($("#openPathInput")?.value || "").trim();
  if (!file && !path) return toast("请先选择或输入一个存档", true);
  if (nationalDraft.dirty && !confirm("打开存档将放弃国家队选拔草稿，继续吗？")) return;
  try {
    const body = file ? { filename: file.name } : { path };
    const loaded = await api("/api/open", { method: "POST", body: JSON.stringify(body) });
    await applySaveAndRefresh(loaded.save_name);
  } catch (error) { toast(error.message, true); }
}

async function openChosenFile() {
  const file = $("#openFileInput")?.files?.[0];
  if (!file) return;
  try {
    const loaded = await api("/api/open", {
      method: "POST",
      body: JSON.stringify({ filename: file.name }),
    });
    await applySaveAndRefresh(loaded.save_name);
  } catch (error) {
    toast(error.message, true);
  }
}

function bindEvents() {
  bindNational();
  $("#quickAge18").addEventListener("click", applyQuickAge18);
  $("#quickRestoreBirthdays").addEventListener("click", restoreQuickBirthdays);
  $("#quickAddLegends").addEventListener("click", addQuickLegends);
  $("#quickPeakRestore").addEventListener("click", restoreQuickPeak);
  $$(".tab").forEach(tab => tab.addEventListener("click", () => switchView(tab.dataset.view)));
  ["#playerSearch", "#nationFilter", "#overallFilter"].forEach(selector => $(selector).addEventListener("input", () => debounce("playerTimer", searchPlayers)));
  $("#playerResults").addEventListener("keydown", handlePlayerResultsKeydown);
  $("#positionFilter").addEventListener("change", searchPlayers);
  $("#teamSearch").addEventListener("input", () => debounce("teamTimer", searchTeams));
  bindTransferPicker("from");
  bindTransferPicker("to");
  bindExactTransferPage();
  $("#swapTransferTeams").addEventListener("click", () => {
    const from = transferPickerInput("from");
    const to = transferPickerInput("to");
    [from.value, to.value] = [to.value, from.value];
    [from.dataset.teamId, to.dataset.teamId] = [to.dataset.teamId, from.dataset.teamId];
    [app.transferSelection.from, app.transferSelection.to] = [app.transferSelection.to, app.transferSelection.from];
    closeTransferSuggestions();
    loadTransferRosters();
  });
  $("#transferFromRoster").addEventListener("click", handleTransferClick);
  $("#transferToRoster").addEventListener("click", handleTransferClick);
  $("#saveButton").addEventListener("click", saveChanges);
  $("#resetButton").addEventListener("click", resetChanges);
  $("#openButton").addEventListener("click", openSaveViaPicker);
  $("#openForm").addEventListener("submit", openSave);
  $("#cancelOpen").addEventListener("click", () => $("#openDialog").close());
  $("#retryPickSave").addEventListener("click", () => {
    $("#openDialog").close();
    openSaveViaPicker();
  });
  $("#openFileInput").addEventListener("change", openChosenFile);
  $("#quickLegendList").addEventListener("click", openLegendList);
  $("#quickPeakList").addEventListener("click", openPeakList);
  $("#closeListDialog").addEventListener("click", () => $("#listDialog").close());
  document.addEventListener("click", event => {
    if (!event.target.closest?.(".transfer-picker")) closeTransferSuggestions();
  });
}

async function init() {
  try {
    app.state = await fetch("/api/state").then(response => response.json());
    app.meta = await api("/api/meta");
    fillMeta();
    bindEvents();
    await refreshState();
    await Promise.all([searchPlayers(), searchTeams(), loadTransferRosters(), loadQuickPanel()]);
  } catch (error) { toast(error.message, true); }
}

const nationalDraft = {
  team: null,
  roster: [],
  dirty: false,
  busy: false,
  request: 0,
  sorts: {
    candidates: { key: "overallrating", direction: "desc" },
    roster: { key: "jerseynumber", direction: "asc" },
  },
};

function nationalSize() {
  return nationalDraft.team?.expected_roster_size || 26;
}

function clearNational() {
  nationalDraft.request++;
  Object.assign(nationalDraft, { team: null, roster: [], dirty: false, busy: false });
  $("#nationalTeam").value = "";
  renderNational();
}

async function loadNational(teamId) {
  const requestId = ++nationalDraft.request;
  nationalDraft.busy = true;
  renderNational();
  try {
    const team = await api(`/api/national-teams/${teamId}`);
    if (requestId !== nationalDraft.request) return;
    Object.assign(nationalDraft, {
      team,
      roster: team.roster.map(player => ({ ...player })),
      dirty: false,
    });
    $("#nationalTeam").value = String(teamId);
  } catch (error) {
    if (requestId === nationalDraft.request) {
      $("#nationalTeam").value = nationalDraft.team?.teamid || "";
      toast(error.message, true);
    }
  } finally {
    if (requestId === nationalDraft.request) {
      nationalDraft.busy = false;
      renderNational();
    }
  }
}

function nationalValidation() {
  if (!nationalDraft.team) return "请选择国家队";
  if (!nationalDraft.team.editable) {
    return `原名单不是 ${nationalSize()} 人，已禁用编辑以保护存档`;
  }
  if (nationalDraft.roster.length !== nationalSize()) {
    return `还需选拔 ${nationalSize() - nationalDraft.roster.length} 人，补足后才能应用`;
  }
  const numbers = nationalDraft.roster.map(player => player.jerseynumber);
  if (numbers.some(number => !Number.isInteger(number) || number < 1 || number > 99)) {
    return "号码必须为 1–99 的整数";
  }
  if (new Set(numbers).size !== numbers.length) return "号码重复，请调整后再应用";
  return "";
}

function updateNationalStatus() {
  const invalid = nationalValidation();
  $("#nationalCount").textContent = `${nationalDraft.roster.length} / ${nationalSize()} 人`;
  $("#nationalStatus").textContent = nationalDraft.busy
    ? "正在处理…"
    : invalid || (nationalDraft.dirty
      ? "草稿尚未应用；应用后请在顶部保存为新存档"
      : "名单完整 · 修改后请先应用，再保存为新存档");
  $("#nationalApply").disabled = nationalDraft.busy || !nationalDraft.dirty || !!invalid;
  $("#nationalReload").disabled = nationalDraft.busy || !nationalDraft.team;
  $("#nationalAutoNumbers").disabled = nationalDraft.busy || !nationalDraft.team?.editable;
  $("#nationalAutoBySort").disabled = nationalDraft.busy || !nationalDraft.team?.editable;
  $("#nationalTeam").disabled = nationalDraft.busy;
}

// FC26 位置 id：0=GK、3=RB/5=CB/7=LB、10=CDM/12=RM/14=CM/16=LM/18=CAM、23=RW/25=ST/27=LW
const NATIONAL_POSITION_GROUPS = ["GK", "DEF", "MID", "ATT"];

function positionGroupOf(player) {
  const raw = player?.position;
  if (typeof raw === "number" && Number.isFinite(raw)) {
    if (raw === 0) return 0;
    if (raw <= 9) return 1;
    if (raw <= 22) return 2;
    return 3;
  }
  const label = String(player?.primary_position || "").toUpperCase();
  if (label === "GK") return 0;
  if (label.endsWith("M")) return 2;
  if (label.endsWith("B") || label === "SW") return 1;
  return 3;
}

function ratingComparator(a, b) {
  return (b.overallrating || 0) - (a.overallrating || 0)
    || String(a.name || "").localeCompare(String(b.name || ""))
    || (a.playerid || 0) - (b.playerid || 0);
}

/**
 * 经典号码表：主力按位置拿固定号码，替补拿剩下的。
 *   门将 1；后卫 2/3/4/5（右后卫→2、左后卫→3、中卫→4/5）；
 *   中场 10/8/6（前腰→10、中前卫→8、后腰→6）；前锋 9/7/11（中锋→9、右路→7、左路→11）。
 * 每个号码优先挑“位置匹配 + 能力最高”的球员，匹配不到就用该组能力最高者。
 */
const CLASSIC_NUMBER_SLOTS = [
  { group: 0, number: 1, hints: ["GK"] },
  { group: 1, number: 2, hints: ["RB", "RWB"] },
  { group: 1, number: 3, hints: ["LB", "LWB"] },
  { group: 1, number: 4, hints: ["CB", "RCB", "LCB"] },
  { group: 1, number: 5, hints: ["CB", "RCB", "LCB"] },
  { group: 2, number: 10, hints: ["CAM", "RAM", "LAM", "CM", "RCM", "LCM"] },
  { group: 2, number: 8, hints: ["CM", "RCM", "LCM", "RM", "LM", "CAM"] },
  { group: 2, number: 6, hints: ["CDM", "RDM", "LDM", "CM"] },
  { group: 3, number: 9, hints: ["ST", "LST", "RST", "CF"] },
  { group: 3, number: 7, hints: ["RW", "RF", "RM"] },
  { group: 3, number: 11, hints: ["LW", "LF", "LM"] },
];

function autoNumberByPositionAndRating() {
  const roster = nationalDraft.roster || [];
  if (!roster.length) return toast("请先选入球员", true);
  const takenIds = new Set();
  const numbers = new Map();

  const pickFor = (slot) => {
    const pool = roster.filter(player =>
      !takenIds.has(player.playerid) && positionGroupOf(player) === slot.group);
    if (!pool.length) return null;
    const labelled = pool.filter(player =>
      slot.hints.includes(String(player.primary_position || "").toUpperCase()));
    return (labelled.length ? labelled : pool).sort(ratingComparator)[0];
  };

  CLASSIC_NUMBER_SLOTS.forEach(slot => {
    const player = pickFor(slot);
    if (!player) return;
    takenIds.add(player.playerid);
    numbers.set(player.playerid, slot.number);
  });

  // 替补：门将 → 后卫 → 中场 → 前锋，组内能力高者在前，拿剩下的号码（升序）
  const substitutes = roster
    .filter(player => !takenIds.has(player.playerid))
    .sort((a, b) => positionGroupOf(a) - positionGroupOf(b) || ratingComparator(a, b));
  const free = [];
  for (let number = 1; number <= roster.length; number += 1) {
    if (![...numbers.values()].includes(number)) free.push(number);
  }
  substitutes.forEach(player => numbers.set(player.playerid, free.shift()));

  roster.forEach(player => {
    const number = numbers.get(player.playerid);
    if (number !== undefined) player.jerseynumber = number;
  });
  nationalDraft.dirty = true;
  renderNational();

  const starters = CLASSIC_NUMBER_SLOTS
    .filter(slot => [...numbers.entries()].some(([id, value]) => value === slot.number))
    .map(slot => slot.number).join("/");
  toast(`已按经典号码编号 ${roster.length} 人（主力 ${starters}，其余为替补号码）`);
}

function autoNumberByCurrentSort() {
  const roster = nationalDraft.roster || [];
  if (!roster.length) return toast("请先选入球员", true);
  sortedRoster(roster, nationalDraft.sorts.roster).forEach((player, index) => {
    player.jerseynumber = index + 1;
  });
  nationalDraft.dirty = true;
  renderNational();
  toast(`已按当前排序编号 ${roster.length} 人`);
}

function nationalSortHeader(side, key, label) {
  const sort = nationalDraft.sorts[side];
  const suffix = sort.key === key ? (sort.direction === "asc" ? " ↑" : " ↓") : " ↕";
  return `<button class="sort-button" data-national-sort="${side}" data-key="${key}">${label}${suffix}</button>`;
}

function renderNational() {
  const team = nationalDraft.team;
  const selected = new Set(nationalDraft.roster.map(player => player.playerid));
  const query = $("#nationalSearch").value.trim().toLocaleLowerCase();
  const minimum = Number($("#nationalOverall").value || 0);
  const position = $("#nationalPosition").value;
  const candidates = (team?.candidates || []).filter(player =>
    !selected.has(player.playerid)
    && `${player.name} ${player.name_cn} ${player.playerid}`.toLocaleLowerCase().includes(query)
    && player.overallrating >= minimum
    && (!position || player.primary_position === position)
  );
  $("#nationalCandidateCount").textContent = `${candidates.length} 人`;
  for (const side of ["candidates", "roster"]) {
    const isRoster = side === "roster";
    const list = sortedRoster(
      isRoster ? nationalDraft.roster : candidates,
      nationalDraft.sorts[side],
    );
    const root = $(isRoster ? "#nationalRoster" : "#nationalCandidates");
    const disabled = nationalDraft.busy || !team?.editable;
    root.innerHTML = `<table class="roster-table"><thead><tr>
      ${isRoster ? `<th>${nationalSortHeader(side, "jerseynumber", "号码")}</th>` : ""}
      <th>球员</th><th>${nationalSortHeader(side, "overallrating", "能力")}</th>
      <th>${nationalSortHeader(side, "primary_position", "位置")}</th><th>操作</th>
      </tr></thead><tbody>${list.map(player => `<tr>
      ${isRoster ? `<td><input class="jersey-input" aria-label="${escapeHtml(player.name)} 的国家队号码" type="number" min="1" max="99" value="${escapeHtml(player.jerseynumber ?? "")}" data-national-number="${player.playerid}" ${disabled ? "disabled" : ""}></td>` : ""}
      <td><strong>${escapeHtml(player.name_cn || player.name)}</strong><small>${escapeHtml(player.name)} · ${player.playerid}</small>${!isRoster ? `<small>${escapeHtml(player.club)}</small>` : ""}</td>
      <td>${escapeHtml(player.overallrating)}</td><td>${escapeHtml(player.primary_position)}</td>
      <td><button class="button ${isRoster ? "ghost" : "primary"}" data-national-${isRoster ? "remove" : "add"}="${player.playerid}" ${disabled || (!isRoster && (selected.size >= nationalSize() || player.unavailable)) ? "disabled" : ""}>${isRoster ? "移出" : player.unavailable ? "已入其他国家队" : "选入"}</button></td>
      </tr>`).join("") || '<tr><td colspan="5">没有符合条件的球员</td></tr>'}</tbody></table>`;
  }
  updateNationalStatus();
}

function bindNational() {
  $("#nationalGenderToggle").addEventListener("click", event => {
    const button = event.target.closest(".gender-option");
    if (!button) return;
    setNationalGender(Number(button.dataset.gender));
  });
  $("#nationalTeam").addEventListener("change", () => {
    const teamId = Number($("#nationalTeam").value);
    if (nationalDraft.dirty && !confirm("切换国家队将放弃当前选拔草稿，继续吗？")) {
      $("#nationalTeam").value = nationalDraft.team.teamid;
      return;
    }
    if (teamId) loadNational(teamId); else clearNational();
  });
  ["#nationalSearch", "#nationalOverall", "#nationalPosition"].forEach(selector => {
    $(selector).addEventListener("input", renderNational);
  });
  $("#nationalView").addEventListener("input", event => {
    const playerId = Number(event.target.dataset.nationalNumber);
    if (!playerId || nationalDraft.busy) return;
    const player = nationalDraft.roster.find(item => item.playerid === playerId);
    if (!player) return;
    player.jerseynumber = event.target.value === "" ? null : Number(event.target.value);
    nationalDraft.dirty = true;
    updateNationalStatus();
  });
  $("#nationalView").addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button || button.disabled || nationalDraft.busy) return;
    const { nationalSort, key, nationalAdd, nationalRemove } = button.dataset;
    if (nationalSort) {
      const sort = nationalDraft.sorts[nationalSort];
      nationalDraft.sorts[nationalSort] = {
        key,
        direction: sort.key === key && sort.direction === "asc" ? "desc" : "asc",
      };
    } else if (nationalAdd && nationalDraft.roster.length < nationalSize()) {
      const player = nationalDraft.team.candidates.find(item => item.playerid === Number(nationalAdd));
      const used = new Set(nationalDraft.roster.map(item => item.jerseynumber));
      let number = 1;
      while (used.has(number)) number++;
      nationalDraft.roster.push({ ...player, jerseynumber: number });
      nationalDraft.dirty = true;
    } else if (nationalRemove) {
      nationalDraft.roster = nationalDraft.roster.filter(item => item.playerid !== Number(nationalRemove));
      nationalDraft.dirty = true;
    } else {
      return;
    }
    renderNational();
  });
  $("#nationalAutoNumbers").addEventListener("click", autoNumberByPositionAndRating);
  $("#nationalAutoBySort").addEventListener("click", autoNumberByCurrentSort);
  $("#nationalReload").addEventListener("click", () => {
    if (!nationalDraft.dirty || confirm("确定放弃当前国家队草稿？")) {
      loadNational(nationalDraft.team.teamid);
    }
  });
  $("#nationalApply").addEventListener("click", async () => {
    if (nationalValidation() || nationalDraft.busy) return;
    nationalDraft.busy = true;
    renderNational();
    try {
      const teamId = nationalDraft.team.teamid;
      await api(`/api/national-teams/${teamId}`, {
        method: "POST",
        body: JSON.stringify({ roster: nationalDraft.roster }),
      });
      nationalDraft.dirty = false;
      await refreshState();
      await loadNational(teamId);
      toast("国家队选拔已应用，请点击顶部“保存为新存档”");
    } catch (error) {
      toast(error.message, true);
    } finally {
      nationalDraft.busy = false;
      renderNational();
    }
  });
  window.addEventListener("beforeunload", event => {
    if (nationalDraft.dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
}

init();
