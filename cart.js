document.addEventListener('DOMContentLoaded', function() {
    // Инициализация корзины
    let cart = JSON.parse(localStorage.getItem('cart')) || [];
    const cartItems = document.getElementById('cartItems');
    const emptyCart = document.getElementById('emptyCart');
    const cartCount = document.getElementById('cartCount');
    const subtotalEl = document.getElementById('subtotal');
    const deliveryEl = document.getElementById('delivery');
    const totalEl = document.getElementById('total');
    const orderForm = document.getElementById('orderForm');
    const dateInput = document.getElementById('date');

    // Установка минимальной даты (сегодня)
    const today = new Date();
    const minDate = today.toISOString().split('T')[0];
    dateInput.min = minDate;

    // Обновление счетчика корзины
    function updateCartCount() {
        const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
        cartCount.textContent = totalItems;
    }

    // Расчет стоимости
    function calculateTotals() {
        const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const delivery = subtotal > 0 ? 300 : 0;
        const total = subtotal + delivery;

        subtotalEl.textContent = subtotal.toLocaleString() + ' ₽';
        deliveryEl.textContent = delivery.toLocaleString() + ' ₽';
        totalEl.textContent = total.toLocaleString() + ' ₽';

        return { subtotal, delivery, total };
    }

    // Отображение товаров в корзине
    function renderCartItems() {
        if (cart.length === 0) {
            emptyCart.style.display = 'block';
            cartItems.innerHTML = '';
            cartItems.appendChild(emptyCart);
            return;
        }

        emptyCart.style.display = 'none';
        cartItems.innerHTML = '';

        cart.forEach((item, index) => {
            const cartItem = document.createElement('div');
            cartItem.className = 'cart-item';
            cartItem.innerHTML = `
                <div class="cart-item-image">
                    <img src="${item.image}" alt="${item.name}" loading="lazy">
                </div>
                <div class="cart-item-details">
                    <div class="cart-item-name">${item.name}</div>
                    <div class="cart-item-price">${item.price.toLocaleString()} ₽/${item.unit}</div>
                </div>
                <div class="cart-item-controls">
                    <div class="quantity-control">
                        <button class="quantity-btn minus" data-index="${index}">-</button>
                        <input type="number" class="quantity-input" value="${item.quantity}" min="1" data-index="${index}">
                        <button class="quantity-btn plus" data-index="${index}">+</button>
                    </div>
                    <button class="remove-item" data-index="${index}">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            cartItems.appendChild(cartItem);
        });

        // Добавляем обработчики событий
        document.querySelectorAll('.quantity-btn.plus').forEach(btn => {
            btn.addEventListener('click', increaseQuantity);
        });

        document.querySelectorAll('.quantity-btn.minus').forEach(btn => {
            btn.addEventListener('click', decreaseQuantity);
        });

        document.querySelectorAll('.quantity-input').forEach(input => {
            input.addEventListener('change', updateQuantity);
        });

        document.querySelectorAll('.remove-item').forEach(btn => {
            btn.addEventListener('click', removeItem);
        });
    }

    // Функции управления количеством
    function increaseQuantity(e) {
        const index = e.target.dataset.index;
        cart[index].quantity++;
        updateCart();
    }

    function decreaseQuantity(e) {
        const index = e.target.dataset.index;
        if (cart[index].quantity > 1) {
            cart[index].quantity--;
            updateCart();
        }
    }

    function updateQuantity(e) {
        const index = e.target.dataset.index;
        const quantity = parseInt(e.target.value);
        if (quantity > 0) {
            cart[index].quantity = quantity;
            updateCart();
        }
    }

    function removeItem(e) {
        const index = e.target.closest('.remove-item').dataset.index;
        cart.splice(index, 1);
        updateCart();
    }

    // Обновление корзины
    function updateCart() {
        localStorage.setItem('cart', JSON.stringify(cart));
        updateCartCount();
        renderCartItems();
        calculateTotals();
    }

    // Обработка формы заказа
    orderForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (cart.length === 0) {
            alert('Добавьте товары в корзину перед оформлением заказа');
            return;
        }

        const formData = new FormData(orderForm);
        const orderData = {
            customer: {
                name: formData.get('name'),
                phone: formData.get('phone'),
                email: formData.get('email'),
                address: formData.get('address')
            },
            delivery: {
                date: formData.get('date'),
                time: formData.get('time')
            },
            comment: formData.get('comment'),
            payment: formData.get('payment'),
            items: cart,
            totals: calculateTotals()
        };

        // Отправка заказа в Telegram
        sendOrderToTelegram(orderData);
    });

    // Отправка заказа на сервер
	
	async function sendOrderToTelegram(orderData) {
		const submitBtn = document.getElementById('submitOrder');
		const originalText = submitBtn.innerHTML;
    
		try {
			// Показываем индикатор загрузки
			submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
			submitBtn.disabled = true;

			const response = await fetch('/api/order', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(orderData)
			});

			const data = await response.json();

			if (response.ok) {
				// Очистка корзины после успешной отправки
				cart = [];
				updateCart();
				showNotification('✅ Заказ успешно оформлен! Мы свяжемся с вами в ближайшее время.');
				
				// Очистка формы
				orderForm.reset();
			} else {
				console.error('Ошибка сервера:', data);
				showNotification('❌ Произошла ошибка при отправке заказа. Пожалуйста, свяжитесь с нами напрямую.', 'error');
			}
		} catch (error) {
			console.error('Ошибка сети:', error);
			showNotification('❌ Не удалось отправить заказ. Проверьте интернет-соединение и попробуйте снова.', 'error');
		} finally {
			// Восстанавливаем кнопку
			submitBtn.innerHTML = originalText;
			submitBtn.disabled = false;
		}
	}
	// Функция для показа уведомлений
	function showNotification(message, type = 'success') {
		const notification = document.createElement('div');
		notification.className = `notification ${type}`;
		notification.innerHTML = `
			<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
			<span>${message}</span>
			<button onclick="this.parentElement.remove()">&times;</button>
		`;
    
		document.body.appendChild(notification);
    
		// Автоматическое удаление через 5 секунд
		setTimeout(() => {
			if (notification.parentElement) {
				notification.remove();
			}
		}, 5000);
	}

    // Функция для экранирования символов Markdown
    function escapeMarkdown(text) {
        return text.toString()
            .replace(/_/g, '\\_')
            .replace(/\*/g, '\\*')
            .replace(/\[/g, '\\[')
            .replace(/\]/g, '\\]')
            .replace(/\(/g, '\\(')
            .replace(/\)/g, '\\)')
            .replace(/~/g, '\\~')
            .replace(/`/g, '\\`')
            .replace(/>/g, '\\>')
            .replace(/#/g, '\\#')
            .replace(/\+/g, '\\+')
            .replace(/-/g, '\\-')
            .replace(/=/g, '\\=')
            .replace(/\|/g, '\\|')
            .replace(/\{/g, '\\{')
            .replace(/\}/g, '\\}')
            .replace(/\./g, '\\.')
            .replace(/!/g, '\\!');
    }

    // Инициализация
    updateCartCount();
    renderCartItems();
    calculateTotals();

    // Мобильное меню (повторяем функционал из script.js)
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const mainNav = document.getElementById('mainNav');
    const navLinks = document.querySelectorAll('.nav-link');
    const body = document.body;

    if (mobileMenuToggle && mainNav) {
        function toggleMenu() {
            mobileMenuToggle.classList.toggle('active');
            mainNav.classList.toggle('active');
            body.classList.toggle('menu-open');
            body.style.overflow = body.classList.contains('menu-open') ? 'hidden' : '';
        }

        mobileMenuToggle.addEventListener('click', toggleMenu);
        navLinks.forEach(link => link.addEventListener('click', () => {
            if (mainNav.classList.contains('active')) toggleMenu();
        }));
    }
});
