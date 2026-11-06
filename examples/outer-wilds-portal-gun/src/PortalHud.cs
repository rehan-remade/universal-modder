using UnityEngine;

namespace OWPortalGun;

/// <summary>
/// Portal 2's crosshair (left arc blue, right arc orange, filled once that portal exists) and short messages.
/// Drawn with IMGUI because the game's notifications only show on the suit's helmet HUD.
/// </summary>
public class PortalHud : MonoBehaviour
{
	private static readonly Color Blue = new(0.25f, 0.62f, 1f, 0.95f);
	private static readonly Color Orange = new(1f, 0.6f, 0.15f, 0.95f);

	private Texture2D _atlas;
	private string _message;
	private float _messageUntil;
	private GUIStyle _style;

	public void Init(GunAssets assets)
	{
		assets.Textures.TryGetValue("portal_crosshairs", out _atlas);
	}

	/// <summary>English or Spanish, following the game's language.</summary>
	public static string T(string en, string es) =>
		TextTranslation.Get() != null && TextTranslation.Get().GetLanguage() == TextTranslation.Language.SPANISH_LA ? es : en;

	public void Show(string text, float seconds = 2.5f)
	{
		_message = text;
		_messageUntil = Time.unscaledTime + seconds;
	}

	// Atlas: 256x64, five 48 px cells (42 px of art + separators): left arc, right arc, left filled, right filled, dot.
	private static Rect Cell(int i) => new((i * 48f + 3f) / 256f, 0f, 42f / 256f, 1f);

	private void OnGUI()
	{
		if (Event.current.type != EventType.Repaint || OWTime.IsPaused())
			return;
		var gun = PortalGun.Instance;
		var sys = PortalSystem.Instance;
		if (gun != null && gun.Equipped && _atlas != null && OWInput.IsInputMode(InputMode.Character))
		{
			var s = Screen.height / 1080f;
			var w = 42f * s * 1.1f;
			var h = 64f * s * 1.1f;
			var c = new Vector2(Screen.width * 0.5f, Screen.height * 0.5f);
			var r = new Rect(c.x - w * 0.5f, c.y - h * 0.5f, w, h);
			var old = GUI.color;
			GUI.color = Blue;
			GUI.DrawTextureWithTexCoords(r, _atlas, Cell(sys != null && sys.Portals[0] != null ? 2 : 0));
			GUI.color = Orange;
			GUI.DrawTextureWithTexCoords(r, _atlas, Cell(sys != null && sys.Portals[1] != null ? 3 : 1));
			GUI.color = old;
		}
		if (_message != null && Time.unscaledTime < _messageUntil)
		{
			_style ??= new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter, fontSize = Mathf.RoundToInt(22 * Screen.height / 1080f) };
			var rect = new Rect(0, Screen.height * 0.72f, Screen.width, 40 * Screen.height / 1080f);
			var a = Mathf.Clamp01(_messageUntil - Time.unscaledTime);
			_style.normal.textColor = new Color(0, 0, 0, 0.8f * a);
			GUI.Label(new Rect(rect.x + 2, rect.y + 2, rect.width, rect.height), _message, _style);
			_style.normal.textColor = new Color(1, 1, 1, a);
			GUI.Label(rect, _message, _style);
		}
	}
}
