// cadastro: confere se as duas senhas são iguais antes de enviar
const formCadastro = document.getElementById("form-cadastro");

if (formCadastro) {
  formCadastro.addEventListener("submit", function (e) {
    const senha = document.getElementById("senha").value;
    const confirmar = document.getElementById("confirmar").value;

    if (senha !== confirmar) {
      e.preventDefault(); // impede o envio do formulário
      alert("As senhas não são iguais.");
    }
  });
}

// relatório: botão de imprimir
const botaoImprimir = document.getElementById("btn-imprimir");

if (botaoImprimir) {
  botaoImprimir.addEventListener("click", function () {
    window.print();
  });
}

// início: desativa o botão enquanto a API responde, para não clicar duas vezes
const formBusca = document.querySelector(".busca");

if (formBusca) {
  formBusca.addEventListener("submit", function () {
    const botao = formBusca.querySelector("button");
    botao.disabled = true;
    botao.textContent = "Buscando...";
  });
}

// mensagens de erro dos campos em português
// o navegador usa o idioma dele por padrão, então troco o texto na mão
const campos = document.querySelectorAll("input");

campos.forEach(function (campo) {
  campo.addEventListener("invalid", function () {
    if (campo.validity.valueMissing) {
      campo.setCustomValidity("Preencha este campo.");
    } else if (campo.validity.typeMismatch) {
      campo.setCustomValidity("Digite um e-mail válido, com @. Ex: nome@email.com");
    } else if (campo.validity.tooShort) {
      campo.setCustomValidity("A senha precisa ter pelo menos 6 caracteres.");
    }
  });

  // sem isso o campo continuaria inválido mesmo depois de corrigido
  campo.addEventListener("input", function () {
    campo.setCustomValidity("");
  });
});
