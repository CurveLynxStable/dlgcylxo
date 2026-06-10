import { spawnSync } from "node:child_process";

const RELEASE_PREFIX = "release/";

function fail(message, code = 1) {
  console.error(`❌ ${message}`);
  process.exit(code);
}

function run(command, args, { capture = false, check = true } = {}) {
  const result = spawnSync(command, args, {
    shell: false,
    encoding: "utf8",
    stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
  });

  if (result.error) {
    fail(`Сбой выполнения: ${command} ${args.join(" ")} (${result.error.message})`);
  }
  if (check && (result.status ?? 1) !== 0) {
    fail(`Команда завершилась с ошибкой: ${command} ${args.join(" ")}`, result.status ?? 1);
  }
  return result;
}

function trimOutput(value) {
  return (value ?? "").replaceAll("\r", "").trim();
}

function assertGitRepo() {
  const result = run("git", ["rev-parse", "--is-inside-work-tree"], {
    capture: true,
    check: false,
  });
  if ((result.status ?? 1) !== 0) {
    fail("Текущий каталог не является git-репозиторием (git rev-parse не удался)", 2);
  }
}

function setupGitflow() {
  assertGitRepo();

  const keysResult = run("git", ["config", "--local", "--get-regexp", "^gitflow\\."], {
    capture: true,
    check: false,
  });

  if ((keysResult.status ?? 1) === 0) {
    const keys = Array.from(
      new Set(
        trimOutput(keysResult.stdout)
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean)
          .map((line) => line.split(/\s+/, 1)[0]),
      ),
    );
    for (const key of keys) {
      run("git", ["config", "--local", "--unset-all", key], { check: false });
    }
  }

  run("git-flow", [
    "init",
    "--preset=classic",
    "--defaults",
    "--main=tauri",
    "--develop=dev",
    "--no-create-branches",
  ]);

  run("git-flow", [
    "config",
    "add",
    "topic",
    "release",
    "tauri",
    "--starting-point=dev",
    "--tag=true",
  ]);

  console.log("✅ Конфигурация git-flow завершена");
}

function parseFinishArgs(argv) {
  const options = {
    version: "",
    remote: "origin",
    mainBranch: "tauri",
    devBranch: "dev",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") {
      printUsage();
      process.exit(0);
    }
    const next = argv[i + 1];
    if (arg === "-v" || arg === "--version" || arg === "--Version") {
      if (!next) fail(`У параметра ${arg} отсутствует значение`, 2);
      options.version = next;
      i += 1;
      continue;
    }
    if (arg.startsWith("--version=") || arg.startsWith("--Version=")) {
      options.version = arg.split("=", 2)[1] ?? "";
      continue;
    }
    if (arg === "-r" || arg === "--remote" || arg === "--Remote") {
      if (!next) fail(`У параметра ${arg} отсутствует значение`, 2);
      options.remote = next;
      i += 1;
      continue;
    }
    if (arg.startsWith("--remote=") || arg.startsWith("--Remote=")) {
      options.remote = arg.split("=", 2)[1] ?? "";
      continue;
    }
    if (arg === "-m" || arg === "--main-branch" || arg === "--MainBranch") {
      if (!next) fail(`У параметра ${arg} отсутствует значение`, 2);
      options.mainBranch = next;
      i += 1;
      continue;
    }
    if (arg.startsWith("--main-branch=") || arg.startsWith("--MainBranch=")) {
      options.mainBranch = arg.split("=", 2)[1] ?? "";
      continue;
    }
    if (arg === "-d" || arg === "--dev-branch" || arg === "--DevBranch") {
      if (!next) fail(`У параметра ${arg} отсутствует значение`, 2);
      options.devBranch = next;
      i += 1;
      continue;
    }
    if (arg.startsWith("--dev-branch=") || arg.startsWith("--DevBranch=")) {
      options.devBranch = arg.split("=", 2)[1] ?? "";
      continue;
    }
    fail(`Неизвестный параметр ${arg}`, 2);
  }

  return options;
}

function finishRelease(argv) {
  assertGitRepo();
  const options = parseFinishArgs(argv);

  const statusResult = run("git", ["status", "--porcelain"], { capture: true, check: false });
  if ((statusResult.status ?? 1) !== 0) {
    fail("Не удалось прочитать git status", 3);
  }
  const dirty = trimOutput(statusResult.stdout);
  if (dirty) {
    console.error(
      "Рабочая копия не чиста (git status --porcelain выводит изменения); сначала выполните commit/stash/clean:",
    );
    for (const line of dirty.split("\n")) {
      if (line.trim()) console.error(`  ${line}`);
    }
    fail("Прервано: рабочая копия не чиста", 20);
  }

  const branchResult = run("git", ["rev-parse", "--abbrev-ref", "HEAD"], {
    capture: true,
    check: false,
  });
  const branch = trimOutput(branchResult.stdout);
  if ((branchResult.status ?? 1) !== 0 || !branch) {
    fail("Не удалось получить имя текущей ветки", 4);
  }
  if (!branch.startsWith(RELEASE_PREFIX)) {
    fail(
      `Текущая ветка не release/* (сейчас '${branch}'). Переключитесь на ветку release/<версия> и запустите снова.`,
      10,
    );
  }

  const currentVersion = branch.slice(RELEASE_PREFIX.length);
  if (!currentVersion) {
    fail(
      `Из имени ветки '${branch}' не удалось извлечь версию (ожидается вид release/2.0.0-beta.10)`,
      11,
    );
  }

  const version = options.version || currentVersion;
  if (options.version && options.version !== currentVersion) {
    fail(
      `Передан -v/-Version '${options.version}', но текущая ветка '${branch}' (версия '${currentVersion}'). Значения не совпадают, прервано.`,
      12,
    );
  }

  const expectedTag = /^[vV]/.test(version) ? version : `v${version}`;
  const expectedRef = `refs/tags/${expectedTag}`;

  const localTagResult = run("git", ["show-ref", "--tags", "--verify", "--quiet", expectedRef], {
    check: false,
  });
  const localTagStatus = localTagResult.status ?? 1;
  if (localTagStatus === 0) {
    fail(
      `Локально уже существует tag: ${expectedTag} (${expectedRef}). Смените версию или сначала удалите этот tag.`,
      30,
    );
  }
  if (localTagStatus !== 1) {
    fail(
      `Проверка локального tag не удалась: git show-ref --tags --verify --quiet ${expectedRef}`,
      30,
    );
  }

  const remoteTagResult = run(
    "git",
    ["ls-remote", "--tags", options.remote, expectedRef, `${expectedRef}^{}`],
    { capture: true, check: false },
  );
  if ((remoteTagResult.status ?? 1) !== 0) {
    fail(
      `Не удалось запросить удалённые tag: git ls-remote --tags ${options.remote} ... (проверьте имя remote/сеть/права)`,
      31,
    );
  }
  if (trimOutput(remoteTagResult.stdout)) {
    fail(
      `На remote '${options.remote}' уже существует tag: ${expectedTag}. Смените версию или удалите tag на remote.`,
      32,
    );
  }

  console.log(`▶ Текущая ветка: ${branch}`);
  console.log(`▶ Будет выполнено: git-flow release finish ${version}`);
  console.log(
    `▶ После завершения push: ${options.remote} ${options.mainBranch} ${options.devBranch} + (HEAD tag if exists)`,
  );

  const finishResult = run("git-flow", ["release", "finish", version], { check: false });
  if ((finishResult.status ?? 1) !== 0) {
    const code = finishResult.status ?? 1;
    fail(`git-flow release finish не удался (exit=${code})`, code);
  }

  const pushBranchesResult = run(
    "git",
    ["push", options.remote, options.mainBranch, options.devBranch],
    { check: false },
  );
  if ((pushBranchesResult.status ?? 1) !== 0) {
    const code = pushBranchesResult.status ?? 1;
    fail(
      `Не удалось отправить ветки: git push ${options.remote} ${options.mainBranch} ${options.devBranch}`,
      code,
    );
  }

  const tagResult = run("git", ["describe", "--tags", "--exact-match"], {
    capture: true,
    check: false,
  });
  const headTag = trimOutput(tagResult.stdout);
  if (headTag) {
    const pushTagResult = run("git", ["push", options.remote, `refs/tags/${headTag}`], {
      check: false,
    });
    if ((pushTagResult.status ?? 1) !== 0) {
      const code = pushTagResult.status ?? 1;
      fail(`Не удалось отправить tag: git push ${options.remote} refs/tags/${headTag}`, code);
    }
    console.log(`✅ Tag отправлен: ${headTag}`);
  } else {
    console.log("ℹ️ На HEAD нет tag, пропускаем push tag");
  }

  const checkoutDevResult = run("git", ["checkout", options.devBranch], { check: false });
  if ((checkoutDevResult.status ?? 1) !== 0) {
    const code = checkoutDevResult.status ?? 1;
    fail(`Не удалось вернуться на ветку разработки: git checkout ${options.devBranch}`, code);
  }
  console.log(`✅ Возврат на ветку: ${options.devBranch}`);

  console.log("✅ Готово");
}

function syncBranches() {
  assertGitRepo();

  const statusResult = run("git", ["status", "--porcelain"], { capture: true, check: false });
  if ((statusResult.status ?? 1) !== 0) {
    fail("Не удалось прочитать git status", 3);
  }
  const dirty = trimOutput(statusResult.stdout);
  if (dirty) {
    console.error(
      "Рабочая копия не чиста (git status --porcelain выводит изменения); сначала выполните commit/stash/clean:",
    );
    for (const line of dirty.split("\n")) {
      if (line.trim()) console.error(`  ${line}`);
    }
    fail("Прервано: рабочая копия не чиста", 20);
  }

  const branches = ["dev", "tauri"];
  for (const branch of branches) {
    const checkoutResult = run("git", ["checkout", branch], { check: false });
    if ((checkoutResult.status ?? 1) !== 0) {
      const code = checkoutResult.status ?? 1;
      fail(`Не удалось переключить ветку: git checkout ${branch}`, code);
    }
    console.log(`▶ Переключено на ветку: ${branch}`);

    const pullResult = run("git", ["pull"], { check: false });
    if ((pullResult.status ?? 1) !== 0) {
      const code = pullResult.status ?? 1;
      fail(`Не удалось выполнить pull ветки: git pull (${branch})`, code);
    }
    console.log(`✅ Ветка обновлена (pull): ${branch}`);
  }

  const checkoutDevResult = run("git", ["checkout", "dev"], { check: false });
  if ((checkoutDevResult.status ?? 1) !== 0) {
    const code = checkoutDevResult.status ?? 1;
    fail("Не удалось вернуться на ветку разработки: git checkout dev", code);
  }
  console.log("✅ Возврат на ветку: dev");
}

function printUsage() {
  console.log("Использование:");
  console.log("  node ./scripts/gitflow.mjs setup");
  console.log("  node ./scripts/gitflow.mjs finish [-v version] [-r remote] [-m main] [-d dev]");
  console.log("  node ./scripts/gitflow.mjs sync");
}

const [command, ...args] = process.argv.slice(2);

if (!command || command === "-h" || command === "--help") {
  printUsage();
  process.exit(0);
}

if (command === "setup") {
  setupGitflow();
  process.exit(0);
}

if (command === "finish") {
  finishRelease(args);
  process.exit(0);
}

if (command === "sync") {
  syncBranches();
  process.exit(0);
}

fail(`Неизвестная подкоманда ${command}`, 2);
