
function checkSniperStatus() {
    fetch('/api/sniper/status')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const isRunning = data.is_running;
                if (isRunning) {
                    $('#sniperStatus').removeClass('bg-red-100 text-red-800')
                        .addClass('bg-green-100 text-green-800')
                        .text('运行中');
                    $('#startSniper').prop('disabled', true).addClass('opacity-50');
                    $('#stopSniper').prop('disabled', false).removeClass('opacity-50');
                } else {
                    $('#sniperStatus').removeClass('bg-green-100 text-green-800')
                        .addClass('bg-red-100 text-red-800')
                        .text('已停止');
                    $('#startSniper').prop('disabled', false).removeClass('opacity-50');
                    $('#stopSniper').prop('disabled', true).addClass('opacity-50');
                }
            }
        });
}

// 修改初始化代码
$(document).ready(function () {
    loadConfig();
    updateWalletList();
    updateContractList();
    loadTransactions();
    checkSniperStatus(); // 初始检查状态

    // 设置定时刷新
    setInterval(() => {
        checkSniperStatus(); // 定期检查状态
        loadTransactions();
    }, 5000);
});

// 修改启动按钮处理函数
$('#startSniper').click(function () {
    if (!confirm('确定要启动狙击吗？')) return;

    const startButton = $(this);
    const originalText = startButton.text();

    showLoading(startButton, '启动中...');

    const mode = $('#snipeMode').val();

    fetch('/api/wallets')
        .then(response => response.json())
        .then(wallets => {
            if (wallets.length === 0) {
                alert('请先添加钱包');
                return Promise.reject('No wallets');
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
                checkSniperStatus(); // 立即检查状态
            }
        })
        .catch(error => {
            if (error !== 'No wallets') {
                alert('启动失败：' + error.message);
            }
        })
        .finally(() => {
            resetButton(startButton, originalText);
        });
});

function openTransferModal(type, walletAddress) {
    currentTransferData = {
        type,
        walletAddress
    };

    const title = type === 'collect' ? '归集操作' : '分发操作';
    $('#modalTitle').text(title);
    $('#tokenAddress').val('');
    $('#transferAmount').val('');
    $('#transferModal').removeClass('hidden');
    $('#confirmTransfer').prop('disabled', false).removeClass('opacity-50');
}

function closeTransferModal() {
    $('#transferModal').addClass('hidden');
    $('#confirmTransfer').prop('disabled', false).removeClass('opacity-50');
    currentTransferData = {
        type: null,
        walletAddress: null
    };
}

function submitTransfer() {
    const tokenAddress = $('#tokenAddress').val().trim();
    const amount = $('#transferAmount').val();
    const confirmButton = $('#confirmTransfer');
    const originalText = confirmButton.text();

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

    // 显示加载状态
    showLoading(confirmButton, '处理中...');
    confirmButton.prop('disabled', true).addClass('opacity-50');

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
                alert(`${currentTransferData.type === 'collect' ? '归集' : '分发'}操作已完成`);
                closeTransferModal();
                loadTransactions();
            } else {
                alert('操作失败：' + data.message);
            }
        })
        .catch(error => {
            alert('操作失败：' + error.message);
        })
        .finally(() => {
            // 恢复按钮状态
            resetButton(confirmButton, originalText);
            confirmButton.prop('disabled', false).removeClass('opacity-50');
        });
}

function showLoading(element, text) {
    const originalHtml = element.html();
    const originalDisabled = element.prop('disabled');

    element.data('original-html', originalHtml)
        .data('original-disabled', originalDisabled)
        .html(`
                <span class="inline-flex items-center">
                    <svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    ${text}
                </span>
            `)
        .prop('disabled', true);
}

function resetButton(element) {
    const originalHtml = element.data('original-html');
    const originalDisabled = element.data('original-disabled');

    if (originalHtml) {
        element.html(originalHtml);
    }
    if (typeof originalDisabled !== 'undefined') {
        element.prop('disabled', originalDisabled);
    }
}


// 钱包列表渲染函数
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


// 添加钱包函数修改
function addWallets() {
    const addresses = $('#walletAddresses').val().trim().split('\n');
    const addButton = $('.bg-blue-500:contains("添加钱包")');

    if (!addresses[0]) {
        alert('请输入钱包私钥');
        return;
    }

    showLoading(addButton, '添加中...');

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
        })
        .finally(() => {
            resetButton(addButton);
        });
}

// 删除钱包函数修改
function deleteWallet(address) {
    const deleteButton = $(`button[onclick="deleteWallet('${address}')"]`);
    showLoading(deleteButton, '删除中...');

    fetch(`/api/wallets?address=${address}`, {
        method: 'DELETE'
    })
        .then(() => updateWalletList())
        .finally(() => {
            resetButton(deleteButton);
        });
}

// 清空钱包函数修改
function clearWallets() {
    if (confirm('确定要清空所有钱包吗？')) {
        const clearButton = $('.bg-gray-500:contains("清空钱包")');
        showLoading(clearButton, '清空中...');

        fetch('/api/wallets', {
            method: 'DELETE'
        })
            .then(() => updateWalletList())
            .finally(() => {
                resetButton(clearButton);
            });
    }
}

// 其他现有代码保持不变...


// 添加模态框状态管理
let currentTransferData = {
    type: null,
    walletAddress: null
};

// 添加全局加载状态管理
let loadingStates = {
    transfer: false,
    wallets: false,
    contracts: false,
    config: false,
    sniper: false
};


// 配置管理
function saveConfig() {
    const saveButton = $('button:contains("保存配置")');
    const originalText = saveButton.text();

    const config = {
        maxSolPerTrade: parseFloat($('#maxSolPerTrade').val()),
        gasFee: parseFloat($('#gasFee').val()),
        sellDelay: parseFloat($('#sellDelay').val()),
        sellPercentage: parseFloat($('#sellPercentage').val())
    };

    showLoading(saveButton, '保存中...');

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
        })
        .finally(() => {
            resetButton(saveButton, originalText);
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


// 更新合约列表渲染函数
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


// 初始化
$(document).ready(function () {
    loadConfig();
    updateWalletList();
    updateContractList();
    loadTransactions();

    // 设置定时刷新
    setInterval(() => {
        if (sniperRunning) {
            loadTransactions();
        }
    }, 5000);

    $('#stopSniper').prop('disabled', true).addClass('opacity-50');
});

// 其他现有代码保持不变...


// 全局变量
let sniperRunning = false;


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
