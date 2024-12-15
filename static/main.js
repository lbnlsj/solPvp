// 添加模态框状态管理
let currentTransferData = {
    type: null,
    walletAddress: null
};

// 更新钱包列表渲染函数
function updateWalletList() {
    fetch('/api/wallets')
        .then(response => response.json())
        .then(wallets => {
            const list = $('#walletList');
            list.empty();
            wallets.forEach(wallet => {
                const shortWallet = `${wallet.slice(0, 6)}...${wallet.slice(-4)}`;
                list.append(`
                    <div class="flex items-center justify-between p-2 border rounded">
                        <div class="flex items-center gap-2">
                            <button onclick="openTransferModal('collect', '${wallet}')" 
                                    class="bg-yellow-500 text-white px-2 py-1 rounded hover:bg-yellow-600">
                                归集
                            </button>
                            <button onclick="openTransferModal('distribute', '${wallet}')" 
                                    class="bg-purple-500 text-white px-2 py-1 rounded hover:bg-purple-600">
                                分发
                            </button>
                            <span title="${wallet}">${shortWallet}</span>
                        </div>
                        <button onclick="deleteWallet('${wallet}')" 
                                class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600">
                            删除
                        </button>
                    </div>
                `);
            });
        });
}

// 打开转账模态框
function openTransferModal(type, walletAddress) {
    currentTransferData = {
        type,
        walletAddress
    };

    // 更新模态框标题
    const title = type === 'collect' ? '归集操作' : '分发操作';
    $('#modalTitle').text(title);

    // 清空输入框
    $('#tokenAddress').val('');
    $('#transferAmount').val('');

    // 显示模态框
    $('#transferModal').removeClass('hidden');
}

// 关闭转账模态框
function closeTransferModal() {
    $('#transferModal').addClass('hidden');
    currentTransferData = {
        type: null,
        walletAddress: null
    };
}

// 提交转账操作
function submitTransfer() {
    const tokenAddress = $('#tokenAddress').val().trim();
    const amount = $('#transferAmount').val();

    if (!tokenAddress || !amount) {
        alert('请填写完整信息');
        return;
    }

    const isSOL = tokenAddress.toUpperCase() === 'SOL';
    const operation = {
        type: currentTransferData.type,
        walletAddress: currentTransferData.walletAddress,
        tokenAddress: isSOL ? 'SOL' : tokenAddress,
        amount: parseFloat(amount),
        isSOL
    };

    fetch(`/api/${currentTransferData.type}_funds`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(operation)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(`${currentTransferData.type === 'collect' ? '归集' : '分发'}操作已提交`);
            closeTransferModal();
        } else {
            alert('操作失败：' + data.message);
        }
    })
    .catch(error => {
        alert('操作失败：' + error.message);
    });
}


// 全局变量
let sniperRunning = false;


// 页面初始化
$(document).ready(function () {
    // 加载配置
    loadConfig();

    // 更新列表显示
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

// 配置管理
function saveConfig() {
    const config = {
        maxSolPerTrade: parseFloat($('#maxSolPerTrade').val()),
        gasFee: parseFloat($('#gasFee').val()),
        sellDelay: parseFloat($('#sellDelay').val()),
        sellPercentage: parseFloat($('#sellPercentage').val())
    };

    fetch('/api/config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(config)
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('配置已保存');
            }
        });
}

function loadConfig() {
    fetch('/api/config')
        .then(response => response.json())
        .then(config => {
            if (config.maxSolPerTrade) $('#maxSolPerTrade').val(config.maxSolPerTrade);
            if (config.gasFee) $('#gasFee').val(config.gasFee);
            if (config.sellDelay) $('#sellDelay').val(config.sellDelay);
            if (config.sellPercentage) $('#sellPercentage').val(config.sellPercentage);
        });
}

// 钱包管理
function addWallets() {
    const addresses = $('#walletAddresses').val().trim().split('\n');

    Promise.all(addresses.map(address => {
        if (!address.trim()) return Promise.resolve();

        return fetch('/api/wallets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({address: address.trim()})
        });
    }))
        .then(() => {
            updateWalletList();
            $('#walletAddresses').val('');
        });
}

function deleteWallet(address) {
    fetch(`/api/wallets?address=${address}`, {
        method: 'DELETE'
    })
        .then(() => updateWalletList());
}

function clearWallets() {
    if (confirm('确定要清空所有钱包吗？')) {
        fetch('/api/wallets', {
            method: 'DELETE'
        })
            .then(() => updateWalletList());
    }
}

// 合约管理
function updateContractList() {
    fetch('/api/contracts')
        .then(response => response.json())
        .then(contracts => {
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
        });
}

function addContracts() {
    const addresses = $('#contractAddresses').val().trim().split('\n');

    Promise.all(addresses.map(address => {
        if (!address.trim()) return Promise.resolve();

        return fetch('/api/contracts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({address: address.trim()})
        });
    }))
        .then(() => {
            updateContractList();
            $('#contractAddresses').val('');
        });
}

function removeContract(address) {
    fetch(`/api/contracts?address=${address}`, {
        method: 'DELETE'
    })
        .then(() => updateContractList());
}

function clearContracts() {
    if (confirm('确定要清空所有合约地址吗？')) {
        fetch('/api/contracts', {
            method: 'DELETE'
        })
            .then(() => updateContractList());
    }
}

// 狙击控制
$('#startSniper').click(function () {
    if (!confirm('确定要启动狙击吗？')) return;

    const mode = $('#snipeMode').val();
    fetch('/api/wallets')
        .then(response => response.json())
        .then(wallets => {
            if (wallets.length === 0) {
                alert('请先添加钱包');
                return;
            }

            const config = {
                mode: mode,
                maxSolPerTrade: parseFloat($('#maxSolPerTrade').val()),
                gasFee: parseFloat($('#gasFee').val()),
                sellDelay: parseInt($('#sellDelay').val(), 10),
                sellPercentage: parseFloat($('#sellPercentage').val())
            };

            return fetch('/api/start_sniper', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });
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
    if (!confirm('确定要停止狙击吗？')) return;

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
                                ${tx.status === '成功' ? 'bg-green-100 text-green-800' : tx.status === '失败' ? 'bg-red-100 text-red-800'
                    : 'bg-yellow-100 text-yellow-800'}">
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
