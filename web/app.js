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

async function saveChanges() {
  try {
    const result = await api("/api/save", { method: "POST", body: "{}" });
    toast(`已生成并验证 ${result.name}`);
    app.selectedPlayer = null;
    app.selectedTeam = null;
    await refreshState();
    await searchPlayers();
    await searchTeams();
    await loadTransferRosters();
  } catch (error) { toast(error.message, true); }
}

async function resetChanges() {
  if (!confirm("确定放弃尚未保存的全部修改吗？")) return;
  try {
    await api("/api/reset", { method: "POST", body: "{}" });
    toast("已放弃全部未保存修改");
    await refreshState();
    if (app.selectedPlayer) await loadPlayer(app.selectedPlayer);
    if (app.selectedTeam) await loadTeam(app.selectedTeam);
    await loadTransferRosters();
  } catch (error) { toast(error.message, true); }
}

async function openSave(event) {
  event.preventDefault();
  const path = $("#openPathInput").value.trim();
  if (!path) return;
  try {
    await api("/api/open", { method: "POST", body: JSON.stringify({ path }) });
    $("#openDialog").close();
    app.selectedPlayer = null;
    app.selectedTeam = null;
    await refreshState();
    await searchPlayers();
    await searchTeams();
    await loadTransferRosters();
    toast("存档已加载");
  } catch (error) { toast(error.message, true); }
}

function bindEvents() {
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
  $("#openButton").addEventListener("click", () => {
    $("#openPathInput").value = app.state.save_path || "";
    $("#openDialog").showModal();
  });
  $("#openForm").addEventListener("submit", openSave);
  $("#cancelOpen").addEventListener("click", () => $("#openDialog").close());
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
    await Promise.all([searchPlayers(), searchTeams()]);
    await loadTransferRosters();
  } catch (error) { toast(error.message, true); }
}

init();
