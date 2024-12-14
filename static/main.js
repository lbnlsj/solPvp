// 全局变量
let wallets = [];
let contracts = [];
let sniperRunning = false;

// 配置管理
function saveConfig() {
    const config = {
        maxSolPerTrade: parseFloat($('#maxSolPerTrade').val()),
        gasFee: parseFloat($('#gasFee').val())
    };

    localStorage.setItem('botConfig', JSON.stringify(config));
    alert('配置已保存');
}

function loadConfig() {
    const config = JSON.parse(localStorage.getItem('botConfig') || '{}');
    if (config.maxSolPerTrade) $('#maxSolPerTrade').val(config.maxSolPerTrade);
    if (config.gasFee) $('#gasFee').val(config.gasFee);
}

function addWallets() {
    const walletInput = document.getElementById("walletAddresses");
    const walletList = document.getElementById("walletList");
    const addresses = walletInput.value.trim().split("\n");

    addresses.forEach(address => {
        if (address) {
            const walletItem = document.createElement("div");
            walletItem.className = "flex items-center justify-between p-2 border rounded";

            walletItem.innerHTML = `
                <div class="flex items-center gap-2">
                    <button onclick="collectFunds('${address}')" class="bg-yellow-500 text-white px-2 py-1 rounded hover:bg-yellow-600">归集</button>
                    <button onclick="distributeFunds('${address}')" class="bg-purple-500 text-white px-2 py-1 rounded hover:bg-purple-600">分发</button>
                    <span>${address}</span>
                </div>
                <button onclick="deleteWallet('${address}', this)" class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600">删除</button>
            `;

            walletList.appendChild(walletItem);
        }
    });

    walletInput.value = ""; // 清空输入框
}

function deleteWallet(address, button) {
    const walletItem = button.parentElement;
    walletItem.remove();
}

function collectFunds(address) {
    alert(`执行归集操作: ${address}`);
    // 在这里添加归集逻辑
}

function distributeFunds(address) {
    alert(`执行分发操作: ${address}`);
    // 在这里添加分发逻辑
}

function clearWallets() {
    if (confirm('确定要清空所有钱包吗？')) {
        wallets = [];
        updateWalletList();
    }
}

function removeWallet(address) {
    wallets = wallets.filter(w => w !== address);
    updateWalletList();
}

function updateWalletList() {
    const list = $('#walletList');
    list.empty();
    wallets.forEach(wallet => {
        list.append(`
            <div class="flex items-center justify-between p-2 border rounded">
                <span class="font-mono text-sm">${wallet}</span>
                <button onclick="removeWallet('${wallet}')" class="text-red-500 hover:text-red-700">
                    删除
                </button>
            </div>
        `);
    });
    localStorage.setItem('wallets', JSON.stringify(wallets));
}

// 合约管理
function addContracts() {
    const addresses = $('#contractAddresses').val().trim().split('\n').filter(a => a.trim());
    addresses.forEach(addr => {
        if (!contracts.includes(addr)) {
            contracts.push(addr);
        }
    });
    updateContractList();
    $('#contractAddresses').val('');
}

function clearContracts() {
    if (confirm('确定要清空所有合约地址吗？')) {
        contracts = [];
        updateContractList();
    }
}

function removeContract(address) {
    contracts = contracts.filter(c => c !== address);
    updateContractList();
}

function updateContractList() {
    const list = $('#contractList');
    list.empty();
    contracts.forEach(contract => {
        list.append(`
            <div class="flex items-center justify-between p-2 border rounded">
                <span class="font-mono text-sm">${contract}</span>
                <button onclick="removeContract('${contract}')" class="text-red-500 hover:text-red-700">
                    删除
                </button>
            </div>
        `);
    });
    localStorage.setItem('contracts', JSON.stringify(contracts));
}

// 狙击控制
$('#startSniper').click(function () {
    const mode = $('#snipeMode').val();
    if (wallets.length === 0) {
        alert('请先添加钱包');
        return;
    }
    if (contracts.length === 0) {
        alert('请先添加监控合约');
        return;
    }

    const config = {
        mode: mode,
        maxSolPerTrade: parseFloat($('#maxSolPerTrade').val()),
        gasFee: parseFloat($('#gasFee').val())
    };

    fetch('/api/start_sniper', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(config)
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                sniperRunning = true;
                $('#sniperStatus').removeClass('bg-red-100 text-red-800')
                    .addClass('bg-green-100 text-green-800')
                    .text('运行中');
                $('#startSniper').prop('disabled', true).addClass('opacity-50');
                $('#stopSniper').prop('disabled', false).removeClass('opacity-50');
            }
        })
        .catch(error => {
            alert('启动失败：' + error.message);
        });
});

$('#stopSniper').click(function () {
    fetch('/api/stop_sniper', {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                sniperRunning = false;
                $('#sniperStatus').removeClass('bg-green-100 text-green-800')
                    .addClass('bg-red-100 text-red-800')
                    .text('已停止');
                $('#startSniper').prop('disabled', false).removeClass('opacity-50');
                $('#stopSniper').prop('disabled', true).addClass('opacity-50');
            }
        })
        .catch(error => {
            alert('停止失败：' + error.message);
        });
});

// 交易记录管理
function loadTransactions() {
    fetch('/api/transactions')
        .then(response => response.json())
        .then(transactions => {
            const list = $('#transactionList');
            list.empty();
            transactions.forEach(tx => {
                list.append(`
                <tr>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">${tx.timestamp}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">${tx.type}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-mono">${tx.token}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">${tx.amount}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full
                            ${tx.status === '成功' ? 'bg-green-100 text-green-800' :
                    tx.status === '失败' ? 'bg-red-100 text-red-800' :
                        'bg-yellow-100 text-yellow-800'}">
                            ${tx.status}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-mono">
${tx.hash ? `<a href="https://solscan.io/tx/${tx.hash}" target="_blank" 
                            class="text-blue-500 hover:text-blue-700">
                            ${tx.hash.slice(0, 8)}...${tx.hash.slice(-6)}
                        </a>` : '-'}
                    </td>
                </tr>
            `);
            });
        });
}

// 页面初始化
$(document).ready(function () {
    // 加载已保存的配置
    loadConfig();

    // 加载已保存的钱包和合约
    wallets = JSON.parse(localStorage.getItem('wallets') || '[]');
    contracts = JSON.parse(localStorage.getItem('contracts') || '[]');
    updateWalletList();
    updateContractList();

    // 加载初始交易记录
    loadTransactions();

    // 设置定时刷新
    setInterval(() => {
        if (sniperRunning) {
            loadTransactions();
        }
    }, 5000);

    // 初始化按钮状态
    $('#stopSniper').prop('disabled', true).addClass('opacity-50');
});